from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID, uuid4

from fastapi import HTTPException
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from services.database.models import DeletionAction, DeletionRequest, LegalHold

from ..core.request_context import RequestContext
from ..core.settings import Settings, get_settings
from ..schemas.completion import DeletionRequestCreate, LegalHoldCreate
from .audit import AuditService
from .job_queue import JobQueueService


class PrivacyCompletionService:
    def __init__(self, session: AsyncSession, context: RequestContext, settings: Settings | None = None) -> None:
        self.session = session
        self.context = context
        self.settings = settings or get_settings()
        self.audit = AuditService(session, context)

    async def create_legal_hold(self, payload: LegalHoldCreate) -> LegalHold:
        item = LegalHold(
            id=uuid4(), tenant_id=self.context.tenant_id,
            resource_type=payload.resource_type, resource_id=payload.resource_id,
            scope_type=payload.scope_type, scope_id=payload.scope_id,
            reason=payload.reason, legal_basis=payload.legal_basis,
            placed_by_user_id=self.context.user_id, placed_at=datetime.now(timezone.utc),
            review_at=payload.review_at,
        )
        self.session.add(item); await self.session.flush()
        await self.audit.record(
            action="privacy.legal_hold_placed", resource_type="legal_hold", resource_id=item.id,
            after_state={"target_type": item.resource_type, "target_id": str(item.resource_id) if item.resource_id else None},
        )
        return item

    async def release_legal_hold(self, hold_id: UUID, reason: str) -> LegalHold:
        item = await self.session.scalar(select(LegalHold).where(
            LegalHold.tenant_id == self.context.tenant_id,
            LegalHold.id == hold_id,
        ).with_for_update())
        if item is None:
            raise HTTPException(status_code=404, detail="Legal hold was not found.")
        if item.released_at is None:
            item.released_at = datetime.now(timezone.utc)
            item.released_by_user_id = self.context.user_id
            item.release_reason = reason
        await self.audit.record(
            action="privacy.legal_hold_released", resource_type="legal_hold", resource_id=item.id,
            after_state={"reason": reason},
        )
        return item

    async def request_deletion(self, payload: DeletionRequestCreate) -> DeletionRequest:
        holds = list(await self.session.scalars(select(LegalHold).where(
            LegalHold.tenant_id == self.context.tenant_id,
            LegalHold.released_at.is_(None),
            or_(
                (LegalHold.resource_type == payload.resource_type) & (LegalHold.resource_id == payload.resource_id),
                LegalHold.scope_type == "institution",
            ),
        )))
        item = DeletionRequest(
            id=uuid4(), tenant_id=self.context.tenant_id,
            resource_type=payload.resource_type, resource_id=payload.resource_id,
            requested_by_user_id=self.context.user_id, reason=payload.reason,
            status="blocked_by_legal_hold" if holds else "preview",
            legal_hold_blocked=bool(holds),
            manifest={
                "legal_hold_ids": [str(hold.id) for hold in holds],
                "planned_components": ["postgresql", "object_storage", "qdrant", "redis_cache", "search_index"],
                "hard_delete_enabled": self.settings.deletion_allow_hard_delete,
            },
        )
        self.session.add(item); await self.session.flush()
        for sequence, component in enumerate(item.manifest["planned_components"], start=1):
            self.session.add(DeletionAction(
                id=uuid4(), tenant_id=self.context.tenant_id, deletion_request_id=item.id,
                sequence_number=sequence, component=component, action="delete_or_anonymise", status="blocked" if holds else "planned",
            ))
        await self.audit.record(
            action="privacy.deletion_requested", resource_type="deletion_request", resource_id=item.id,
            after_state={"resource_type": payload.resource_type, "legal_hold_blocked": bool(holds)},
        )
        return item

    async def approve_deletion(self, request_id: UUID, *, approve: bool, reason: str) -> DeletionRequest:
        item = await self.session.scalar(select(DeletionRequest).where(
            DeletionRequest.tenant_id == self.context.tenant_id,
            DeletionRequest.id == request_id,
        ).with_for_update())
        if item is None:
            raise HTTPException(status_code=404, detail="Deletion request was not found.")
        if item.legal_hold_blocked:
            raise HTTPException(status_code=409, detail="The deletion is blocked by an active legal hold.")
        if self.settings.deletion_require_second_approver and item.requested_by_user_id == self.context.user_id:
            raise HTTPException(status_code=409, detail="A second authorised person must approve this deletion request.")
        if not approve:
            item.status = "rejected"
            item.manifest = {**item.manifest, "rejection_reason": reason}
            return item
        item.status = "approved"
        item.approved_by_user_id = self.context.user_id
        item.approved_at = datetime.now(timezone.utc)
        await JobQueueService(self.session).enqueue(
            tenant_id=self.context.tenant_id,
            job_type="privacy.execute_deletion",
            payload={"deletion_request_id": str(item.id)},
            requested_by_user_id=self.context.user_id,
            correlation_id=self.context.correlation_id,
            idempotency_key=f"deletion:{item.id}",
        )
        await self.audit.record(
            action="privacy.deletion_approved", resource_type="deletion_request", resource_id=item.id,
            after_state={"reason": reason},
        )
        return item
