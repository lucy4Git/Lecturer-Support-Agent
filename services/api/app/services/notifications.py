from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from services.database.models import Notification

from ..core.request_context import RequestContext
from .job_queue import JobQueueService


class NotificationService:
    """Create tenant-owned, recipient-specific, non-secret workspace notifications."""

    def __init__(self, session: AsyncSession, context: RequestContext) -> None:
        self.session = session
        self.context = context

    async def emit(
        self,
        *,
        recipient_user_id: UUID,
        notification_type: str,
        title: str,
        body: str,
        severity: str = "information",
        action_path: str | None = None,
        resource_type: str | None = None,
        resource_id: UUID | None = None,
        expires_at: datetime | None = None,
        metadata: dict | None = None,
    ) -> Notification:
        item = Notification(
            id=uuid4(),
            tenant_id=self.context.tenant_id,
            recipient_user_id=recipient_user_id,
            notification_type=notification_type,
            title=title,
            body=body,
            severity=severity,
            action_path=action_path,
            resource_type=resource_type,
            resource_id=resource_id,
            expires_at=expires_at,
            notification_metadata=metadata or {},
        )
        self.session.add(item)
        await self.session.flush()
        await JobQueueService(self.session).enqueue(
            tenant_id=self.context.tenant_id,
            job_type="notifications.dispatch",
            payload={
                "notification_ids": [str(item.id)],
                "channels": ["in_app"],
                "requested_by_role_code": self.context.role_code,
            },
            requested_by_user_id=self.context.user_id,
            correlation_id=self.context.correlation_id,
            idempotency_key=f"notification-delivery:{item.id}:in_app",
        )
        return item
