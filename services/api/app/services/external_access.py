from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID, uuid4

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from services.database.models import AccessExpiryEvent, ExternalAccessGrant

from ..core.request_context import RequestContext
from .audit import AuditService
from .notifications import NotificationService
from .job_queue import JobQueueService


class ExternalAccessService:
    def __init__(self, session: AsyncSession, context: RequestContext) -> None:
        self.session = session
        self.context = context
        self.audit = AuditService(session, context)
        self.notifications = NotificationService(session, context)

    async def create_grant(
        self,
        *,
        external_user_id: UUID,
        purpose: str,
        starts_at: datetime,
        expires_at: datetime,
        allowed_actions: list[str],
        resource_scope: dict,
    ) -> ExternalAccessGrant:
        if expires_at <= starts_at:
            raise ValueError("External access expiry must be later than its start time.")
        if expires_at <= datetime.now(timezone.utc):
            raise ValueError("External access cannot be created already expired.")
        if not allowed_actions or not resource_scope:
            raise ValueError("External access must be action-limited and resource-scoped.")
        grant = ExternalAccessGrant(
            id=uuid4(),
            tenant_id=self.context.tenant_id,
            external_user_id=external_user_id,
            granted_by_user_id=self.context.user_id,
            purpose=purpose,
            status="active" if starts_at <= datetime.now(timezone.utc) else "pending",
            starts_at=starts_at,
            expires_at=expires_at,
            allowed_actions=allowed_actions,
            resource_scope=resource_scope,
        )
        self.session.add(grant)
        self.session.add(
            AccessExpiryEvent(
                id=uuid4(),
                tenant_id=self.context.tenant_id,
                external_access_grant_id=grant.id,
                scheduled_for=expires_at,
                details={"automatic": True},
            )
        )
        await self.session.flush()
        await self.audit.record(
            action="external_access.granted",
            resource_type="external_access_grant",
            resource_id=grant.id,
            after_state={
                "external_user_id": str(external_user_id),
                "expires_at": expires_at.isoformat(),
                "allowed_actions": allowed_actions,
                "resource_scope": resource_scope,
            },
        )
        await self.notifications.emit(
            recipient_user_id=external_user_id,
            notification_type="temporary_access_granted",
            title="Temporary review access granted",
            body=f"Your restricted access is available until {expires_at.isoformat()}. Only the assigned actions and resources are permitted.",
            severity="warning",
            action_path="action:reviewTasks",
            resource_type="external_access_grant",
            resource_id=grant.id,
            expires_at=expires_at,
            metadata={"allowed_actions": allowed_actions, "resource_scope": resource_scope},
        )
        await JobQueueService(self.session).enqueue(
            tenant_id=self.context.tenant_id,
            job_type="external_access.expire",
            payload={
                "grant_id": str(grant.id),
                "requested_by_role_code": self.context.role_code,
            },
            requested_by_user_id=self.context.user_id,
            correlation_id=self.context.correlation_id,
            idempotency_key=f"external-access-expire:{grant.id}",
            available_at=expires_at,
        )
        return grant

    async def revoke_grant(self, grant_id: UUID, reason: str) -> ExternalAccessGrant:
        grant = await self.session.scalar(
            select(ExternalAccessGrant).where(
                ExternalAccessGrant.tenant_id == self.context.tenant_id,
                ExternalAccessGrant.id == grant_id,
            ).with_for_update()
        )
        if grant is None:
            raise HTTPException(status_code=404, detail="External access grant not found.")
        if grant.status in {"revoked", "expired"}:
            return grant
        grant.status = "revoked"
        grant.revoked_at = datetime.now(timezone.utc)
        grant.revoked_by_user_id = self.context.user_id
        await self.audit.record(
            action="external_access.revoked",
            resource_type="external_access_grant",
            resource_id=grant.id,
            metadata={"reason": reason},
        )
        await self.notifications.emit(
            recipient_user_id=grant.external_user_id,
            notification_type="temporary_access_revoked",
            title="Temporary review access revoked",
            body="Your temporary review access has been revoked. Contact the assigning institution if clarification is required.",
            severity="critical",
            resource_type="external_access_grant",
            resource_id=grant.id,
            metadata={"reason": reason},
        )
        await self.session.flush()
        return grant

    async def expire_due_grants(self, at: datetime | None = None) -> int:
        at = at or datetime.now(timezone.utc)
        grants = (
            await self.session.scalars(
                select(ExternalAccessGrant)
                .where(
                    ExternalAccessGrant.tenant_id == self.context.tenant_id,
                    ExternalAccessGrant.status.in_(["pending", "active"]),
                    ExternalAccessGrant.expires_at <= at,
                )
                .with_for_update(skip_locked=True)
            )
        ).all()
        for grant in grants:
            grant.status = "expired"
            events = list(
                await self.session.scalars(
                    select(AccessExpiryEvent).where(
                        AccessExpiryEvent.tenant_id == self.context.tenant_id,
                        AccessExpiryEvent.external_access_grant_id == grant.id,
                        AccessExpiryEvent.processed_at.is_(None),
                    )
                )
            )
            for event in events:
                event.processed_at = at
                event.outcome = "expired"
                event.details = {**event.details, "processed_automatically": True}
            await self.audit.record(
                action="external_access.expired",
                resource_type="external_access_grant",
                resource_id=grant.id,
            )
        await self.session.flush()
        return len(grants)
