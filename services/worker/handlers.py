from __future__ import annotations

import csv
import hashlib
import io
import json
from collections.abc import Awaitable, Callable
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import delete, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from services.api.app.core.request_context import RequestContext
from services.api.app.core.settings import get_settings
from services.api.app.ingestion.embeddings import OllamaEmbeddingClient
from services.api.app.integrations.object_storage import S3ObjectStorage
from services.api.app.integrations.qdrant import QdrantGateway
from services.api.app.integrations.academic_systems import build_academic_adapter
from services.api.app.services.messaging import MessagingService
from services.api.app.ai.source_discovery import CrossrefSourceDiscovery, OpenAlexSourceDiscovery
from services.worker.backup_execution import BackupExecutor, RestoreDrillExecutor
from services.api.app.services.document_ingestion import DocumentIngestionService
from services.api.app.services.export_generation import ExportRenderer, safe_export_filename
from services.database.models import (
    AIRequest,
    AuditEvent,
    AuditExportJob,
    BackgroundJob,
    Conversation,
    Document,
    DocumentVersion,
    DocumentChunk,
    ExtractedContent,
    ExportJob,
    ExternalAccessGrant,
    AccessExpiryEvent,
    GeneratedOutput,
    ModelExecution,
    Notification,
    NotificationDelivery,
    OutboxEvent,
    OutputVersion,
    ReportRun,
    RetentionRule,
    RetentionRun,
    RetentionRunItem,
    ReviewCycle,
    StorageObject,
    OutboundMessage,
    IntegrationConnection,
    IntegrationSyncRun,
    ExternalRecordMapping,
    DeletionRequest,
    DeletionAction,
    LegalHold,
    DatasetSourceRecord,
    DatasetAcquisitionRun,
    UserFeedback,
    EvaluationResponse,
    BackupRun,
    RestoreDrill,
)
from services.database.models.enums import ExportAudience, ExportFormat, ExportStatus

JobHandler = Callable[[AsyncSession, BackgroundJob], Awaitable[dict[str, Any]]]


def _uuid(value: Any, field: str) -> UUID:
    try:
        return UUID(str(value))
    except (TypeError, ValueError, AttributeError) as exc:
        raise ValueError(f"{field} must be a valid UUID") from exc


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _context(job: BackgroundJob) -> RequestContext:
    user_id = job.requested_by_user_id or _uuid(job.payload.get("requested_by_user_id"), "requested_by_user_id")
    return RequestContext(
        tenant_id=job.tenant_id,
        user_id=user_id,
        role_code=str(job.payload.get("requested_by_role_code") or "system_worker"),
        correlation_id=job.correlation_id or f"job:{job.id}",
        request_id=f"worker:{job.id}",
    )


async def _system_audit(
    session: AsyncSession,
    job: BackgroundJob,
    *,
    action: str,
    resource_type: str,
    resource_id: UUID | None,
    metadata: dict[str, Any] | None = None,
) -> None:
    event = AuditEvent(
        id=uuid4(), tenant_id=job.tenant_id, occurred_at=_now(),
        actor_user_id=job.requested_by_user_id, actor_role_code="system_worker",
        action=action, resource_type=resource_type, resource_id=resource_id,
        correlation_id=job.correlation_id or f"job:{job.id}", request_id=f"worker:{job.id}",
        source_ip_hash=None, before_state=None, after_state=None,
        metadata_payload={"background_job_id": str(job.id), **(metadata or {})},
    )
    session.add(event)
    session.add(
        OutboxEvent(
            id=uuid4(), tenant_id=job.tenant_id, aggregate_type=resource_type,
            aggregate_id=resource_id or event.id, event_type=action,
            payload={"audit_event_id": str(event.id), "background_job_id": str(job.id)},
            correlation_id=job.correlation_id or f"job:{job.id}",
        )
    )


async def dispatch_notifications_handler(session: AsyncSession, job: BackgroundJob) -> dict[str, Any]:
    """Record real in-app delivery; unsupported outbound channels remain visibly blocked."""
    requested_ids = {_uuid(value, "notification_id") for value in job.payload.get("notification_ids", [])}
    channels = tuple(dict.fromkeys(job.payload.get("channels") or ["in_app"]))
    limit = min(max(int(job.payload.get("limit", 100)), 1), 1000)
    query = select(Notification).where(
        Notification.tenant_id == job.tenant_id,
        Notification.archived_at.is_(None),
        or_(Notification.expires_at.is_(None), Notification.expires_at > _now()),
    )
    if requested_ids:
        query = query.where(Notification.id.in_(requested_ids))
    notifications = list(await session.scalars(query.order_by(Notification.created_at).limit(limit)))
    delivered = blocked = reused = 0
    now = _now()
    for notification in notifications:
        for channel in channels:
            existing = await session.scalar(
                select(NotificationDelivery).where(
                    NotificationDelivery.tenant_id == job.tenant_id,
                    NotificationDelivery.notification_id == notification.id,
                    NotificationDelivery.channel == channel,
                )
            )
            if existing and existing.status == "delivered":
                reused += 1
                continue
            delivery = existing or NotificationDelivery(
                id=uuid4(), tenant_id=job.tenant_id,
                notification_id=notification.id, channel=channel,
                status="pending", attempt_count=0, delivery_metadata={},
            )
            if existing is None:
                session.add(delivery)
            delivery.attempt_count += 1
            if channel == "in_app":
                delivery.status = "delivered"
                delivery.delivered_at = now
                delivery.provider_reference = f"notification:{notification.id}"
                delivery.last_error_code = None
                delivery.last_error_detail = None
                delivery.delivery_metadata = {**delivery.delivery_metadata, "transport": "workspace_database"}
                delivered += 1
            else:
                delivery.status = "blocked"
                delivery.last_error_code = "delivery_adapter_not_configured"
                delivery.last_error_detail = (
                    f"The {channel} delivery adapter is not configured; the in-app notification remains available."
                )
                delivery.delivery_metadata = {**delivery.delivery_metadata, "requires_owner_configuration": True}
                blocked += 1
    await _system_audit(
        session, job, action="notifications.dispatch_completed",
        resource_type="notification_delivery", resource_id=None,
        metadata={"delivered": delivered, "blocked": blocked, "reused": reused},
    )
    await session.flush()
    return {"selected": len(notifications), "delivered": delivered, "blocked": blocked, "reused": reused}


async def publish_outbox_handler(session: AsyncSession, job: BackgroundJob) -> dict[str, Any]:
    """Acknowledge unpublished events on the internal durable event stream."""
    requested_ids = {_uuid(value, "outbox_event_id") for value in job.payload.get("outbox_event_ids", [])}
    limit = min(max(int(job.payload.get("limit", 200)), 1), 1000)
    query = select(OutboxEvent).where(
        OutboxEvent.tenant_id == job.tenant_id,
        OutboxEvent.published_at.is_(None),
    )
    if requested_ids:
        query = query.where(OutboxEvent.id.in_(requested_ids))
    events = list(await session.scalars(query.order_by(OutboxEvent.created_at).with_for_update(skip_locked=True).limit(limit)))
    now = _now()
    for event in events:
        event.publish_attempts += 1
        event.published_at = now
        event.last_error = None
        event.payload = {**event.payload, "published_transport": "internal_database", "published_by_job_id": str(job.id)}
    await session.flush()
    return {"published": len(events), "transport": "internal_database"}


async def expire_external_access_handler(session: AsyncSession, job: BackgroundJob) -> dict[str, Any]:
    at = datetime.fromisoformat(job.payload["at"]) if job.payload.get("at") else _now()
    grants = list(
        await session.scalars(
            select(ExternalAccessGrant).where(
                ExternalAccessGrant.tenant_id == job.tenant_id,
                ExternalAccessGrant.status.in_(["pending", "active"]),
                ExternalAccessGrant.expires_at <= at,
            ).with_for_update(skip_locked=True)
        )
    )
    for grant in grants:
        grant.status = "expired"
        events = list(await session.scalars(select(AccessExpiryEvent).where(
            AccessExpiryEvent.tenant_id == job.tenant_id,
            AccessExpiryEvent.external_access_grant_id == grant.id,
            AccessExpiryEvent.processed_at.is_(None),
        )))
        for event in events:
            event.processed_at = at
            event.outcome = "expired"
            event.details = {**event.details, "processed_by_job_id": str(job.id)}
        notification = Notification(
            id=uuid4(), tenant_id=job.tenant_id, recipient_user_id=grant.external_user_id,
            notification_type="temporary_access_expired", title="Temporary review access expired",
            body="Your time-limited review access has expired and no longer permits access to the assigned resources.",
            severity="warning", resource_type="external_access_grant", resource_id=grant.id,
            notification_metadata={"expired_at": at.isoformat()},
        )
        session.add(notification)
        await _system_audit(session, job, action="external_access.expired", resource_type="external_access_grant", resource_id=grant.id)
    await session.flush()
    return {"expired_grants": len(grants), "evaluated_at": at.isoformat()}


async def apply_retention_handler(session: AsyncSession, job: BackgroundJob) -> dict[str, Any]:
    """Apply only allow-listed, reversible dispositions; hard deletion is intentionally unsupported."""
    dry_run = bool(job.payload.get("dry_run", True))
    now = _now()
    run_id = _uuid(job.payload["retention_run_id"], "retention_run_id") if job.payload.get("retention_run_id") else uuid4()
    run = await session.scalar(select(RetentionRun).where(RetentionRun.tenant_id == job.tenant_id, RetentionRun.id == run_id))
    if run is None:
        run = RetentionRun(
            id=run_id, tenant_id=job.tenant_id, requested_by_user_id=job.requested_by_user_id,
            status="running", dry_run=dry_run, evaluated_at=now, summary={},
        )
        session.add(run)
    else:
        run.status = "running"; run.evaluated_at = now; run.dry_run = dry_run
    rules = list(await session.scalars(select(RetentionRule).where(
        RetentionRule.tenant_id == job.tenant_id, RetentionRule.is_active.is_(True)
    )))
    max_candidates = min(max(int(job.payload.get("max_candidates", 1000)), 1), 5000)
    candidates = actions = skipped = 0
    by_resource: dict[str, int] = {}
    for rule in rules:
        cutoff = now - timedelta(days=rule.retention_days)
        resource_key = rule.resource_type.lower().strip()
        rows: list[Any] = []
        safe_action = None
        if resource_key in {"notification", "notifications", "governance.notifications"}:
            rows = list(await session.scalars(select(Notification).where(
                Notification.tenant_id == job.tenant_id,
                Notification.created_at <= cutoff,
                Notification.archived_at.is_(None),
            ).limit(max_candidates - candidates)))
            safe_action = "archive"
        elif resource_key in {"report_run", "report_runs", "analytics.report_runs"}:
            rows = list(await session.scalars(select(ReportRun).where(
                ReportRun.tenant_id == job.tenant_id,
                ReportRun.created_at <= cutoff,
                ReportRun.status.in_(["completed", "failed"]),
            ).limit(max_candidates - candidates)))
            safe_action = "expire"
        elif resource_key in {"audit_export", "audit_export_job", "audit.audit_export_jobs"}:
            rows = list(await session.scalars(select(AuditExportJob).where(
                AuditExportJob.tenant_id == job.tenant_id,
                AuditExportJob.created_at <= cutoff,
                AuditExportJob.status.in_(["completed", "failed"]),
            ).limit(max_candidates - candidates)))
            safe_action = "expire"
        else:
            continue
        for row in rows:
            candidates += 1
            requested = rule.disposition_action.lower().strip()
            status = "planned" if dry_run else "applied"
            reason = f"Retention rule {rule.id} reached its {rule.retention_days}-day threshold."
            if requested not in {safe_action, "review"}:
                status = "skipped"; skipped += 1
                reason += " Requested disposition is not an allow-listed reversible action."
            elif not dry_run and requested != "review":
                if isinstance(row, Notification):
                    row.archived_at = now
                else:
                    row.status = "expired"
                actions += 1
            item = RetentionRunItem(
                id=uuid4(), tenant_id=job.tenant_id, retention_run_id=run.id,
                retention_rule_id=rule.id, resource_type=rule.resource_type,
                resource_id=row.id, disposition_action=requested, status=status,
                reason=reason, evaluated_at=now, applied_at=now if status == "applied" else None,
                item_metadata={"cutoff": cutoff.isoformat(), "dry_run": dry_run},
            )
            session.add(item)
            by_resource[rule.resource_type] = by_resource.get(rule.resource_type, 0) + 1
            if candidates >= max_candidates:
                break
        if candidates >= max_candidates:
            break
    run.status = "completed"
    run.completed_at = _now()
    run.candidate_count = candidates
    run.action_count = actions
    run.skipped_count = skipped
    run.summary = {"by_resource": by_resource, "hard_delete_supported": False, "dry_run": dry_run}
    await _system_audit(session, job, action="retention.run_completed", resource_type="retention_run", resource_id=run.id, metadata=run.summary)
    await session.flush()
    return {"retention_run_id": str(run.id), "candidate_count": candidates, "action_count": actions, "skipped_count": skipped, "dry_run": dry_run}


async def generate_report_handler(session: AsyncSession, job: BackgroundJob) -> dict[str, Any]:
    run_id = _uuid(job.payload.get("report_run_id"), "report_run_id")
    run = await session.scalar(select(ReportRun).where(ReportRun.tenant_id == job.tenant_id, ReportRun.id == run_id).with_for_update())
    if run is None:
        raise ValueError("The requested report run does not exist in this tenant")
    if run.status == "completed":
        return {"report_run_id": str(run.id), "status": "completed", "reused": True}
    run.status = "running"; run.started_at = run.started_at or _now(); run.error_code = None; run.error_detail = None
    start = datetime.fromisoformat(run.parameters.get("period_start")) if run.parameters.get("period_start") else _now() - timedelta(days=30)
    end = datetime.fromisoformat(run.parameters.get("period_end")) if run.parameters.get("period_end") else _now()
    if start.tzinfo is None: start = start.replace(tzinfo=timezone.utc)
    if end.tzinfo is None: end = end.replace(tzinfo=timezone.utc)
    conversation_query = select(func.count(Conversation.id)).where(Conversation.tenant_id == job.tenant_id, Conversation.created_at >= start, Conversation.created_at <= end)
    if run.scope_type == "user" and run.scope_id:
        conversation_query = conversation_query.where(Conversation.owner_user_id == run.scope_id)
    conversations = int(await session.scalar(conversation_query) or 0)
    outputs_query = select(func.count(GeneratedOutput.id)).join(Conversation, Conversation.id == GeneratedOutput.conversation_id).where(
        GeneratedOutput.tenant_id == job.tenant_id, GeneratedOutput.created_at >= start, GeneratedOutput.created_at <= end
    )
    if run.scope_type == "user" and run.scope_id:
        outputs_query = outputs_query.where(Conversation.owner_user_id == run.scope_id)
    outputs = int(await session.scalar(outputs_query) or 0)
    documents_query = select(func.count(Document.id)).where(Document.tenant_id == job.tenant_id, Document.created_at >= start, Document.created_at <= end)
    if run.scope_type == "user" and run.scope_id:
        documents_query = documents_query.where(Document.owner_user_id == run.scope_id)
    documents = int(await session.scalar(documents_query) or 0)
    reviews = int(await session.scalar(select(func.count(ReviewCycle.id)).where(ReviewCycle.tenant_id == job.tenant_id, ReviewCycle.created_at >= start, ReviewCycle.created_at <= end)) or 0)
    model_runs = int(await session.scalar(select(func.count(ModelExecution.id)).where(ModelExecution.tenant_id == job.tenant_id, ModelExecution.created_at >= start, ModelExecution.created_at <= end)) or 0)
    payload = {
        "report_type": run.report_type,
        "scope": {"scope_type": run.scope_type, "scope_id": str(run.scope_id) if run.scope_id else None},
        "period_start": start.isoformat(), "period_end": end.isoformat(),
        "metrics": {"conversations": conversations, "generated_outputs": outputs, "documents": documents, "review_cycles": reviews, "model_executions": model_runs},
        "generated_by": "durable_background_worker",
    }
    encoded = json.dumps(payload, sort_keys=True).encode("utf-8")
    run.result_payload = payload; run.result_sha256 = hashlib.sha256(encoded).hexdigest()
    run.status = "completed"; run.completed_at = _now()
    await _system_audit(session, job, action="report.generated", resource_type="report_run", resource_id=run.id, metadata={"sha256": run.result_sha256})
    await session.flush()
    return {"report_run_id": str(run.id), "status": run.status, "result_sha256": run.result_sha256}


async def generate_audit_export_handler(session: AsyncSession, job: BackgroundJob) -> dict[str, Any]:
    export_id = _uuid(job.payload.get("audit_export_job_id"), "audit_export_job_id")
    export = await session.scalar(select(AuditExportJob).where(AuditExportJob.tenant_id == job.tenant_id, AuditExportJob.id == export_id).with_for_update())
    if export is None:
        raise ValueError("Audit export job not found")
    if export.status == "completed":
        return {"audit_export_job_id": str(export.id), "status": "completed", "reused": True}
    export.status = "running"
    filters = export.filters or {}
    query = select(AuditEvent).where(AuditEvent.tenant_id == job.tenant_id)
    if filters.get("start_at"): query = query.where(AuditEvent.occurred_at >= datetime.fromisoformat(filters["start_at"]))
    if filters.get("end_at"): query = query.where(AuditEvent.occurred_at <= datetime.fromisoformat(filters["end_at"]))
    if filters.get("actor_user_id"): query = query.where(AuditEvent.actor_user_id == _uuid(filters["actor_user_id"], "actor_user_id"))
    if filters.get("action"): query = query.where(AuditEvent.action.ilike(f"%{str(filters['action']).strip()}%"))
    if filters.get("resource_type"): query = query.where(AuditEvent.resource_type == filters["resource_type"])
    events = list(await session.scalars(query.order_by(AuditEvent.occurred_at.desc()).limit(5000)))
    rows = [{"id": str(item.id), "occurred_at": item.occurred_at.isoformat(), "actor_user_id": str(item.actor_user_id) if item.actor_user_id else None, "actor_role_code": item.actor_role_code, "action": item.action, "resource_type": item.resource_type, "resource_id": str(item.resource_id) if item.resource_id else None, "correlation_id": item.correlation_id} for item in events]
    if export.output_format == "csv":
        buffer = io.StringIO(); fields = list(rows[0]) if rows else ["id", "occurred_at", "actor_user_id", "actor_role_code", "action", "resource_type", "resource_id", "correlation_id"]
        writer = csv.DictWriter(buffer, fieldnames=fields); writer.writeheader(); writer.writerows(rows)
        result = {"encoding": "utf-8", "content": buffer.getvalue()}
    else:
        result = {"events": rows}
    export.result_payload = result
    export.result_sha256 = hashlib.sha256(json.dumps(result, sort_keys=True).encode()).hexdigest()
    export.record_count = len(rows); export.status = "completed"; export.generated_at = _now(); export.error_detail = None
    await _system_audit(session, job, action="audit.export.generated", resource_type="audit_export_job", resource_id=export.id, metadata={"record_count": len(rows)})
    await session.flush()
    return {"audit_export_job_id": str(export.id), "status": export.status, "record_count": len(rows), "result_sha256": export.result_sha256}


async def ingest_document_handler(session: AsyncSession, job: BackgroundJob) -> dict[str, Any]:
    version_id = _uuid(job.payload.get("document_version_id"), "document_version_id")
    settings = get_settings(); storage = S3ObjectStorage(settings); embeddings = OllamaEmbeddingClient(settings); qdrant = QdrantGateway(settings)
    try:
        outcome = await DocumentIngestionService(
            session, storage, _context(job), settings=settings,
            embedding_client=embeddings, qdrant=qdrant,
        ).process_version(version_id, force=bool(job.payload.get("force", False)))
        return {"document_version_id": str(version_id), "status": outcome.status, "chunk_count": outcome.chunk_count, "indexed_chunk_count": outcome.indexed_chunk_count}
    finally:
        await embeddings.close(); await qdrant.close()


async def generate_export_handler(session: AsyncSession, job: BackgroundJob) -> dict[str, Any]:
    export_id = _uuid(job.payload.get("export_job_id"), "export_job_id")
    export = await session.scalar(select(ExportJob).where(ExportJob.tenant_id == job.tenant_id, ExportJob.id == export_id).with_for_update())
    if export is None:
        raise ValueError("Export job not found")
    if export.status == ExportStatus.COMPLETED.value:
        return {"export_job_id": str(export.id), "status": export.status, "reused": True}
    row = (await session.execute(
        select(GeneratedOutput, OutputVersion).join(OutputVersion, OutputVersion.id == export.output_version_id).where(
            GeneratedOutput.tenant_id == job.tenant_id,
            OutputVersion.tenant_id == job.tenant_id,
            GeneratedOutput.id == export.generated_output_id,
        )
    )).first()
    if row is None:
        raise ValueError("Generated output or immutable version not found")
    output, version = row
    export.status = ExportStatus.GENERATING.value
    renderer = ExportRenderer(); export_format = ExportFormat(export.export_format); audience = ExportAudience(export.audience)
    rendered = renderer.render(title=output.title, markdown=version.content_text, export_format=export_format, audience=audience)
    filename = safe_export_filename(output.title, rendered.extension)
    storage = S3ObjectStorage(get_settings())
    stored = await storage.put_bytes(
        tenant_id=job.tenant_id,
        object_key=f"tenants/{job.tenant_id}/generated-outputs/{output.id}/versions/{version.version_number}/exports/{export.id}/{filename}",
        content=rendered.content, media_type=rendered.media_type,
        metadata={"generated-output-id": str(output.id), "output-version-id": str(version.id), "audience": audience.value},
    )
    storage_row = StorageObject(
        id=uuid4(), tenant_id=job.tenant_id, provider="s3", bucket_name=stored.bucket_name,
        object_key=stored.object_key, storage_version_id=stored.storage_version_id,
        etag=stored.etag, sha256=stored.sha256, size_bytes=stored.size_bytes, media_type=stored.media_type,
    )
    session.add(storage_row); await session.flush()
    export.storage_object_id = storage_row.id; export.filename = filename; export.media_type = rendered.media_type
    export.size_bytes = len(rendered.content); export.status = ExportStatus.COMPLETED.value; export.generated_at = _now()
    await _system_audit(session, job, action="teaching_output.exported", resource_type="export_job", resource_id=export.id, metadata={"format": export.export_format, "audience": export.audience})
    await session.flush()
    return {"export_job_id": str(export.id), "status": export.status, "filename": filename, "sha256": stored.sha256}



async def deliver_email_handler(session: AsyncSession, job: BackgroundJob) -> dict[str, Any]:
    message_id = _uuid(job.payload.get("outbound_message_id"), "outbound_message_id")
    message = await session.scalar(select(OutboundMessage).where(
        OutboundMessage.tenant_id == job.tenant_id,
        OutboundMessage.id == message_id,
    ).with_for_update())
    if message is None:
        raise ValueError("Outbound message was not found")
    if message.status == "sent":
        return {"outbound_message_id": str(message.id), "status": "sent", "reused": True}
    await MessagingService(session, settings=get_settings()).deliver(message)
    await _system_audit(
        session, job, action="communications.email_delivery_finished",
        resource_type="outbound_message", resource_id=message.id,
        metadata={"status": message.status, "provider": message.provider},
    )
    if message.status == "failed":
        raise RuntimeError(message.last_error or "Email delivery failed")
    return {"outbound_message_id": str(message.id), "status": message.status, "provider": message.provider}


async def integration_sync_handler(session: AsyncSession, job: BackgroundJob) -> dict[str, Any]:
    run_id = _uuid(job.payload.get("sync_run_id"), "sync_run_id")
    run = await session.scalar(select(IntegrationSyncRun).where(
        IntegrationSyncRun.tenant_id == job.tenant_id,
        IntegrationSyncRun.id == run_id,
    ).with_for_update())
    if run is None:
        raise ValueError("Integration sync run was not found")
    connection = await session.scalar(select(IntegrationConnection).where(
        IntegrationConnection.tenant_id == job.tenant_id,
        IntegrationConnection.id == run.connection_id,
    ))
    if connection is None:
        raise ValueError("Integration connection was not found")
    run.status = "running"; run.started_at = run.started_at or _now()
    adapter = build_academic_adapter(
        integration_type=connection.integration_type,
        base_url=connection.base_url,
        secret_reference=connection.secret_reference,
        configuration=connection.configuration,
        settings=get_settings(),
    )
    records, next_cursor = await adapter.pull(
        run.sync_type, cursor=run.cursor,
        limit=get_settings().integration_max_records_per_sync,
    )
    staged: list[dict[str, Any]] = []
    for record in records:
        external_id = str(record.get("id") or record.get("sourcedId") or record.get("idnumber") or "").strip()
        if not external_id:
            run.records_failed += 1
            continue
        staged.append(record)
        mapping = await session.scalar(select(ExternalRecordMapping).where(
            ExternalRecordMapping.tenant_id == job.tenant_id,
            ExternalRecordMapping.connection_id == connection.id,
            ExternalRecordMapping.external_type == run.sync_type,
            ExternalRecordMapping.external_id == external_id,
        ))
        if mapping is None:
            # A deterministic placeholder local identifier records the staging relationship;
            # domain-specific import approval is still required before academic records are changed.
            mapping = ExternalRecordMapping(
                id=uuid4(), tenant_id=job.tenant_id, connection_id=connection.id,
                external_type=run.sync_type, external_id=external_id,
                local_type="staged_external_record",
                local_id=uuid4(), external_version=str(record.get("dateLastModified") or record.get("updated_at") or "") or None,
                mapping_metadata={"staged": True, "record_hash": hashlib.sha256(json.dumps(record, sort_keys=True, default=str).encode()).hexdigest()},
            )
            session.add(mapping)
        run.records_written += 1
    run.records_read = len(records); run.cursor = next_cursor
    run.status = "completed"; run.completed_at = _now()
    run.result_payload = {
        "staged_records": staged[:100],
        "staged_record_count": len(staged),
        "domain_import_applied": False,
        "next_cursor": next_cursor,
    }
    connection.status = "active"; connection.last_test_status = "passed"; connection.last_tested_at = _now()
    await _system_audit(session, job, action="integration.sync_completed", resource_type="integration_sync_run", resource_id=run.id, metadata={"records_read": run.records_read, "records_staged": run.records_written})
    return {"sync_run_id": str(run.id), "status": run.status, "records_read": run.records_read, "records_staged": run.records_written}


async def execute_deletion_handler(session: AsyncSession, job: BackgroundJob) -> dict[str, Any]:
    request_id = _uuid(job.payload.get("deletion_request_id"), "deletion_request_id")
    request = await session.scalar(select(DeletionRequest).where(
        DeletionRequest.tenant_id == job.tenant_id,
        DeletionRequest.id == request_id,
    ).with_for_update())
    if request is None:
        raise ValueError("Deletion request was not found")
    if request.status == "completed":
        return {"deletion_request_id": str(request.id), "status": "completed", "reused": True}
    active_hold = await session.scalar(select(LegalHold.id).where(
        LegalHold.tenant_id == job.tenant_id,
        LegalHold.released_at.is_(None),
        or_(
            (LegalHold.resource_type == request.resource_type) & (LegalHold.resource_id == request.resource_id),
            LegalHold.scope_type == "institution",
        ),
    ).limit(1))
    if active_hold:
        request.status = "blocked_by_legal_hold"; request.legal_hold_blocked = True
        raise RuntimeError("Deletion became blocked by an active legal hold")

    actions = list(await session.scalars(select(DeletionAction).where(
        DeletionAction.tenant_id == job.tenant_id,
        DeletionAction.deletion_request_id == request.id,
    ).order_by(DeletionAction.sequence_number)))
    settings = get_settings()
    low_risk_models = {"user_feedback": UserFeedback, "evaluation_response": EvaluationResponse, "outbound_message": OutboundMessage}

    if not settings.deletion_allow_hard_delete:
        request.status = "approved_pending_owner_execution"
        for action in actions:
            action.status = "owner_machine_required" if action.component != "redis_cache" else "planned"
        request.manifest = {**request.manifest, "execution_boundary": "hard deletion disabled by deployment policy"}
        return {"deletion_request_id": str(request.id), "status": request.status, "hard_delete_performed": False}

    if request.resource_type == "document_version":
        version = await session.scalar(select(DocumentVersion).where(
            DocumentVersion.tenant_id == job.tenant_id, DocumentVersion.id == request.resource_id,
        ).with_for_update())
        if version is None:
            request.status = "completed"; request.completed_at = _now()
            return {"deletion_request_id": str(request.id), "status": request.status, "already_absent": True}
        storage_record = await session.scalar(select(StorageObject).where(
            StorageObject.tenant_id == job.tenant_id, StorageObject.id == version.storage_object_id,
        ).with_for_update())
        if storage_record is None:
            raise RuntimeError("The document version storage record is missing")
        if storage_record.legal_hold or (storage_record.retention_until and storage_record.retention_until > _now()):
            request.status = "blocked_by_storage_retention"
            raise RuntimeError("The storage object is protected by a legal hold or retention period")

        qdrant = QdrantGateway(settings)
        try:
            await qdrant.delete_document_version(tenant_id=job.tenant_id, document_version_id=version.id)
        finally:
            await qdrant.close()
        storage = S3ObjectStorage(settings)
        deleted_version_id = await storage.delete_version(
            object_key=storage_record.object_key, version_id=storage_record.storage_version_id
        )
        await session.execute(delete(DocumentChunk).where(
            DocumentChunk.tenant_id == job.tenant_id, DocumentChunk.document_version_id == version.id
        ))
        await session.execute(delete(ExtractedContent).where(
            ExtractedContent.tenant_id == job.tenant_id, ExtractedContent.document_version_id == version.id
        ))
        evidence = hashlib.sha256(
            f"{job.tenant_id}:{version.id}:{storage_record.object_key}:{deleted_version_id}".encode()
        ).hexdigest()
        storage_record.deleted_at = _now(); storage_record.deletion_evidence_sha256 = evidence
        version.extracted_text_status = "deleted"; version.indexed_at = None; version.status = "archived"
        version.provenance = {**version.provenance, "physical_deletion": {
            "request_id": str(request.id), "performed_at": _now().isoformat(), "evidence_sha256": evidence,
            "content_removed": True, "audit_tombstone_retained": True,
        }}
        document = await session.scalar(select(Document).where(
            Document.tenant_id == job.tenant_id, Document.id == version.document_id
        ).with_for_update())
        if document is not None and document.current_version_id == version.id:
            document.current_version_id = version.previous_version_id
            if version.previous_version_id is None:
                document.is_deleted = True; document.deleted_at = _now()
        for action in actions:
            action.status = "completed" if action.component in {"postgresql", "object_storage", "qdrant", "search_index"} else "not_applicable"
            action.completed_at = _now(); action.evidence_sha256 = evidence
        request.status = "completed"; request.completed_at = _now()
        request.manifest = {**request.manifest, "deletion_evidence_sha256": evidence, "audit_tombstone_retained": True}
        await _system_audit(session, job, action="privacy.document_version_content_deleted", resource_type="deletion_request", resource_id=request.id, metadata={"document_version_id": str(version.id), "evidence_sha256": evidence})
        return {"deletion_request_id": str(request.id), "status": request.status, "hard_delete_performed": True, "evidence_sha256": evidence}

    model = low_risk_models.get(request.resource_type)
    if model is None:
        request.status = "approved_pending_owner_execution"
        for action in actions:
            action.status = "owner_machine_required"
        request.manifest = {**request.manifest, "execution_boundary": "resource type requires a reviewed deletion adapter"}
        return {"deletion_request_id": str(request.id), "status": request.status, "hard_delete_performed": False}

    target = await session.scalar(select(model).where(model.tenant_id == job.tenant_id, model.id == request.resource_id).with_for_update())
    if target is not None:
        await session.delete(target)
    evidence = hashlib.sha256(f"{request.resource_type}:{request.resource_id}:deleted".encode()).hexdigest()
    for action in actions:
        if action.component == "postgresql":
            action.status = "completed"; action.completed_at = _now(); action.evidence_sha256 = evidence
        else:
            action.status = "not_applicable"
    request.status = "completed"; request.completed_at = _now()
    await _system_audit(session, job, action="privacy.deletion_completed", resource_type="deletion_request", resource_id=request.id, metadata={"resource_type": request.resource_type, "evidence_sha256": evidence})
    return {"deletion_request_id": str(request.id), "status": request.status, "hard_delete_performed": True, "evidence_sha256": evidence}


async def acquire_dataset_handler(session: AsyncSession, job: BackgroundJob) -> dict[str, Any]:
    run_id = _uuid(job.payload.get("acquisition_run_id"), "acquisition_run_id")
    run = await session.scalar(select(DatasetAcquisitionRun).where(
        DatasetAcquisitionRun.tenant_id == job.tenant_id,
        DatasetAcquisitionRun.id == run_id,
    ).with_for_update())
    if run is None:
        raise ValueError("Dataset acquisition run was not found")
    source = await session.scalar(select(DatasetSourceRecord).where(
        DatasetSourceRecord.tenant_id == job.tenant_id,
        DatasetSourceRecord.id == run.source_record_id,
    ))
    if source is None or source.approval_status != "approved":
        raise ValueError("Dataset source is not approved")
    run.status = "running"; run.started_at = run.started_at or _now()
    query = str(job.payload.get("query") or source.title)
    limit = min(int(job.payload.get("limit") or 100), 1000)
    settings = get_settings()
    if source.provider.lower() == "openalex":
        records = await OpenAlexSourceDiscovery(settings).discover(query, limit=min(limit, 10))
    elif source.provider.lower() == "crossref":
        records = await CrossrefSourceDiscovery(settings).discover(query, limit=min(limit, 10))
    else:
        raise ValueError("Only approved OpenAlex and Crossref metadata acquisition is automated in v2.5")
    lines = [json.dumps(record.model_dump(mode="json"), sort_keys=True) for record in records]
    content = ("\n".join(lines) + ("\n" if lines else "")).encode("utf-8")
    digest = hashlib.sha256(content).hexdigest()
    storage = S3ObjectStorage(settings)
    stored = await storage.put_bytes(
        tenant_id=job.tenant_id,
        object_key=f"tenants/{job.tenant_id}/datasets/{source.source_key}/{run.id}/metadata.jsonl",
        content=content,
        media_type="application/x-ndjson",
        metadata={"source-key": source.source_key, "licence-code": source.licence_code or "unknown", "intended-use": source.intended_use},
    )
    run.status = "completed"; run.completed_at = _now(); run.records_acquired = len(records)
    run.storage_prefix = stored.object_key
    run.checksum_manifest = {**run.checksum_manifest, "sha256": digest, "object_version_id": stored.storage_version_id, "records": len(records)}
    await _system_audit(session, job, action="data.acquisition_completed", resource_type="dataset_acquisition_run", resource_id=run.id, metadata={"records": len(records), "sha256": digest})
    return {"acquisition_run_id": str(run.id), "status": run.status, "records_acquired": len(records), "sha256": digest}


async def backup_handler(session: AsyncSession, job: BackgroundJob) -> dict[str, Any]:
    run_id = _uuid(job.payload.get("backup_run_id"), "backup_run_id")
    run = await session.scalar(
        select(BackupRun).where(
            BackupRun.tenant_id == job.tenant_id, BackupRun.id == run_id
        ).with_for_update()
    )
    if run is None:
        raise ValueError("Backup run was not found")
    run.status = "running"
    run.started_at = run.started_at or _now()
    include_database = run.backup_type in {"database", "full"}
    include_object_storage = bool(job.payload.get("include_object_storage", True)) and run.backup_type in {"content", "full"}
    include_vector_store = bool(job.payload.get("include_vector_store", True)) and run.backup_type in {"vectors", "full"}
    executor = BackupExecutor(get_settings())
    try:
        destination, results, manifest_sha = await executor.execute(
            tenant_id=job.tenant_id,
            run_id=run.id,
            session=session,
            include_database=include_database,
            include_object_storage=include_object_storage,
            include_vector_store=include_vector_store,
            attempt=max(job.attempt_count, 1),
        )
    except Exception as exc:
        run.status = "failed"
        run.completed_at = _now()
        run.error_detail = str(exc)[:4000]
        await _system_audit(
            session, job, action="operations.backup_failed", resource_type="backup_run",
            resource_id=run.id, metadata={"error": run.error_detail}
        )
        raise
    run.status = "completed"
    run.completed_at = _now()
    run.storage_location = str(destination)
    run.manifest_sha256 = manifest_sha
    run.component_results = results
    await _system_audit(
        session, job, action="operations.backup_completed", resource_type="backup_run",
        resource_id=run.id, metadata={"manifest_sha256": manifest_sha, "components": list(results)}
    )
    return {
        "backup_run_id": str(run.id), "status": run.status,
        "storage_location": run.storage_location, "manifest_sha256": manifest_sha,
        "component_results": results,
    }


async def restore_drill_handler(session: AsyncSession, job: BackgroundJob) -> dict[str, Any]:
    drill_id = _uuid(job.payload.get("restore_drill_id"), "restore_drill_id")
    drill = await session.scalar(
        select(RestoreDrill).where(
            RestoreDrill.tenant_id == job.tenant_id, RestoreDrill.id == drill_id
        ).with_for_update()
    )
    if drill is None:
        raise ValueError("Restore drill was not found")
    backup = await session.scalar(
        select(BackupRun).where(
            BackupRun.tenant_id == job.tenant_id, BackupRun.id == drill.backup_run_id
        )
    )
    if backup is None or backup.status != "completed" or not backup.storage_location:
        raise ValueError("A completed backup is required for a restore drill")
    drill.status = "running"
    drill.started_at = drill.started_at or _now()
    try:
        results = await RestoreDrillExecutor(get_settings()).execute(
            Path(backup.storage_location), drill.isolated_environment or "unspecified"
        )
    except Exception as exc:
        drill.status = "failed"
        drill.completed_at = _now()
        drill.error_detail = str(exc)[:4000]
        await _system_audit(
            session, job, action="operations.restore_drill_failed", resource_type="restore_drill",
            resource_id=drill.id, metadata={"error": drill.error_detail}
        )
        raise
    drill.status = str(results.get("status") or "completed")
    drill.completed_at = _now()
    drill.validation_results = results
    await _system_audit(
        session, job, action="operations.restore_drill_completed", resource_type="restore_drill",
        resource_id=drill.id, metadata={"status": drill.status, "files_verified": results.get("files_verified")}
    )
    return {"restore_drill_id": str(drill.id), **results}


HANDLERS: dict[str, JobHandler] = {
    "notifications.dispatch": dispatch_notifications_handler,
    "outbox.publish": publish_outbox_handler,
    "external_access.expire": expire_external_access_handler,
    "governance.apply_retention": apply_retention_handler,
    "analytics.generate_report": generate_report_handler,
    "audit.generate_export": generate_audit_export_handler,
    "content.ingest_document": ingest_document_handler,
    "content.generate_export": generate_export_handler,
    "operations.backup": backup_handler,
    "operations.restore_drill": restore_drill_handler,
    "communications.deliver_email": deliver_email_handler,
    "integrations.sync": integration_sync_handler,
    "privacy.execute_deletion": execute_deletion_handler,
    "data.acquire_dataset": acquire_dataset_handler,
}
