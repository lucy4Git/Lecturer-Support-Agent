from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID, uuid4

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from services.database.models import DatasetAcquisitionRun, DatasetSourceRecord

from ..core.request_context import RequestContext
from ..schemas.completion import DatasetSourceCreate
from .audit import AuditService
from .job_queue import JobQueueService


class DataPreparationService:
    def __init__(self, session: AsyncSession, context: RequestContext) -> None:
        self.session = session
        self.context = context
        self.audit = AuditService(session, context)

    async def create_source(self, payload: DatasetSourceCreate) -> DatasetSourceRecord:
        if await self.session.scalar(select(DatasetSourceRecord.id).where(
            DatasetSourceRecord.tenant_id == self.context.tenant_id,
            DatasetSourceRecord.source_key == payload.source_key,
        )):
            raise HTTPException(status_code=409, detail="Dataset source key already exists.")
        item = DatasetSourceRecord(
            id=uuid4(), tenant_id=self.context.tenant_id,
            source_key=payload.source_key, title=payload.title, provider=payload.provider,
            canonical_url=payload.canonical_url, licence_code=payload.licence_code,
            licence_url=payload.licence_url, commercial_use_allowed=payload.commercial_use_allowed,
            ai_training_allowed=payload.ai_training_allowed, intended_use=payload.intended_use,
            disciplines=payload.disciplines, provenance=payload.provenance,
        )
        self.session.add(item); await self.session.flush()
        return item

    async def approve_source(self, source_id: UUID, *, approve: bool, note: str) -> DatasetSourceRecord:
        item = await self.session.scalar(select(DatasetSourceRecord).where(
            DatasetSourceRecord.tenant_id == self.context.tenant_id,
            DatasetSourceRecord.id == source_id,
        ).with_for_update())
        if item is None:
            raise HTTPException(status_code=404, detail="Dataset source was not found.")
        item.approval_status = "approved" if approve else "rejected"
        item.approved_by_user_id = self.context.user_id if approve else None
        item.approved_at = datetime.now(timezone.utc) if approve else None
        item.provenance = {**item.provenance, "review_note": note}
        return item

    async def request_acquisition(self, source_id: UUID, *, limit: int, query: str | None) -> DatasetAcquisitionRun:
        source = await self.session.scalar(select(DatasetSourceRecord).where(
            DatasetSourceRecord.tenant_id == self.context.tenant_id,
            DatasetSourceRecord.id == source_id,
        ))
        if source is None:
            raise HTTPException(status_code=404, detail="Dataset source was not found.")
        if source.approval_status != "approved":
            raise HTTPException(status_code=409, detail="Dataset acquisition requires an approved source record.")
        if source.intended_use == "adaptation" and source.ai_training_allowed is not True:
            raise HTTPException(status_code=409, detail="This source is not approved for model adaptation or training.")
        run = DatasetAcquisitionRun(
            id=uuid4(), tenant_id=self.context.tenant_id, source_record_id=source.id,
            status="queued", requested_by_user_id=self.context.user_id,
            checksum_manifest={"query": query, "limit": limit, "licence_code": source.licence_code},
        )
        self.session.add(run); await self.session.flush()
        await JobQueueService(self.session).enqueue(
            tenant_id=self.context.tenant_id,
            job_type="data.acquire_dataset",
            payload={"acquisition_run_id": str(run.id), "query": query, "limit": limit},
            requested_by_user_id=self.context.user_id,
            correlation_id=self.context.correlation_id,
            idempotency_key=f"dataset-acquisition:{run.id}",
        )
        await self.audit.record(
            action="data.acquisition_requested", resource_type="dataset_acquisition_run", resource_id=run.id,
            after_state={"source_key": source.source_key, "intended_use": source.intended_use},
        )
        return run
