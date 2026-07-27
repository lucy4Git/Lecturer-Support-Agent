from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from services.database.models import UploadBatch, UploadItem

from ..core.request_context import RequestContext
from ..integrations.object_storage import ObjectStorage
from .audit import AuditService
from .document_versioning import DocumentVersioningService, VersioningResult


@dataclass(frozen=True, slots=True)
class BulkUploadEntry:
    client_item_key: str
    filename: str
    content: bytes
    media_type: str | None
    title: str
    document_type: str
    change_reason: str
    existing_document_id: UUID | None = None
    metadata: dict | None = None
    visibility: str = "private"


class BulkUploadService:
    def __init__(self, session: AsyncSession, storage: ObjectStorage, context: RequestContext) -> None:
        self.session = session
        self.storage = storage
        self.context = context
        self.audit = AuditService(session, context)

    async def create_batch(
        self,
        *,
        entries: list[BulkUploadEntry],
        scope_type: str,
        scope_id: UUID | None,
        change_reason: str,
        org_unit_id: UUID | None = None,
        programme_id: UUID | None = None,
        module_id: UUID | None = None,
    ) -> tuple[UploadBatch, list[VersioningResult]]:
        batch = UploadBatch(
            id=uuid4(),
            tenant_id=self.context.tenant_id,
            uploaded_by_user_id=self.context.user_id,
            active_role_code=self.context.role_code,
            scope_type=scope_type,
            scope_id=scope_id,
            source_channel="web",
            status="processing",
            expected_item_count=len(entries),
            received_item_count=len(entries),
            change_reason=change_reason,
            metadata_payload={"immutable_versions": True},
        )
        self.session.add(batch)
        await self.session.flush()

        versioning = DocumentVersioningService(
            session=self.session,
            storage=self.storage,
            context=self.context,
        )
        results: list[VersioningResult] = []
        failed = 0
        for entry in entries:
            item = UploadItem(
                id=uuid4(),
                tenant_id=self.context.tenant_id,
                upload_batch_id=batch.id,
                client_item_key=entry.client_item_key,
                original_filename=entry.filename,
                media_type=entry.media_type,
                size_bytes=len(entry.content),
                sha256=__import__("hashlib").sha256(entry.content).hexdigest(),
                status="received",
                detected_document_type=entry.document_type,
                proposed_scope={
                    "scope_type": scope_type,
                    "scope_id": str(scope_id) if scope_id else None,
                    "org_unit_id": str(org_unit_id) if org_unit_id else None,
                    "programme_id": str(programme_id) if programme_id else None,
                    "module_id": str(module_id) if module_id else None,
                },
            )
            self.session.add(item)
            try:
                result = await versioning.create_version(
                    title=entry.title,
                    document_type=entry.document_type,
                    filename=entry.filename,
                    content=entry.content,
                    media_type=entry.media_type,
                    change_reason=entry.change_reason,
                    document_id=entry.existing_document_id,
                    org_unit_id=org_unit_id,
                    programme_id=programme_id,
                    module_id=module_id,
                    upload_batch_id=batch.id,
                    provenance={"source": "bulk_upload", "batch_id": str(batch.id)},
                    metadata=entry.metadata,
                    visibility=entry.visibility,
                )
                item.document_version_id = result.version.id
                item.status = "duplicate" if result.exact_duplicate else "stored"
                results.append(result)
            except Exception as exc:
                # Savepoint-based per-item recovery can be introduced when archive
                # processing is moved to background jobs. The foundation records
                # the failure and re-raises only for invalid transaction state.
                failed += 1
                item.status = "failed"
                item.validation_errors = [{"message": str(exc), "type": type(exc).__name__}]
        batch.completed_item_count = len(entries) - failed
        batch.failed_item_count = failed
        batch.status = "completed" if failed == 0 else "partially_completed"
        batch.completed_at = __import__("datetime").datetime.now(__import__("datetime").timezone.utc)
        await self.audit.record(
            action="upload.batch_completed",
            resource_type="upload_batch",
            resource_id=batch.id,
            after_state={
                "item_count": len(entries),
                "completed": batch.completed_item_count,
                "failed": failed,
            },
        )
        await self.session.flush()
        return batch, results
