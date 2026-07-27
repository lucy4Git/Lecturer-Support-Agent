from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from services.database.models import AuditEvent, OutboxEvent

from ..core.request_context import RequestContext
from .job_queue import JobQueueService


class AuditService:
    def __init__(self, session: AsyncSession, context: RequestContext) -> None:
        self.session = session
        self.context = context

    async def record(
        self,
        *,
        action: str,
        resource_type: str,
        resource_id: UUID | None,
        before_state: dict[str, Any] | None = None,
        after_state: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
        event_type: str | None = None,
    ) -> AuditEvent:
        event = AuditEvent(
            id=uuid4(),
            tenant_id=self.context.tenant_id,
            occurred_at=datetime.now(timezone.utc),
            actor_user_id=self.context.user_id,
            actor_role_code=self.context.role_code,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            correlation_id=self.context.correlation_id,
            request_id=self.context.request_id,
            source_ip_hash=self.context.source_ip_hash,
            before_state=before_state,
            after_state=after_state,
            metadata_payload=metadata or {},
        )
        self.session.add(event)
        outbox = OutboxEvent(
            id=uuid4(),
            tenant_id=self.context.tenant_id,
            aggregate_type=resource_type,
            aggregate_id=resource_id or event.id,
            event_type=event_type or action,
            payload={"audit_event_id": str(event.id), **(metadata or {})},
            correlation_id=self.context.correlation_id,
        )
        self.session.add(outbox)
        await self.session.flush()
        await JobQueueService(self.session).enqueue(
            tenant_id=self.context.tenant_id,
            job_type="outbox.publish",
            payload={
                "outbox_event_ids": [str(outbox.id)],
                "requested_by_role_code": self.context.role_code,
            },
            requested_by_user_id=self.context.user_id,
            correlation_id=self.context.correlation_id,
            idempotency_key=f"outbox-publish:{outbox.id}",
        )
        return event
