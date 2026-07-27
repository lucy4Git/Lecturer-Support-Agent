from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from services.database.models import OutboundMessage

from ..core.request_context import RequestContext
from ..core.sensitive_content import SensitiveContentProtector
from ..core.settings import Settings, get_settings
from ..integrations.email_delivery import EmailGateway, build_email_gateway
from .audit import AuditService
from .job_queue import JobQueueService


class MessagingService:
    def __init__(
        self,
        session: AsyncSession,
        context: RequestContext | None = None,
        settings: Settings | None = None,
        gateway: EmailGateway | None = None,
    ) -> None:
        self.session = session
        self.context = context
        self.settings = settings or get_settings()
        self.gateway = gateway or build_email_gateway(self.settings)
        self.protector = SensitiveContentProtector(self.settings)

    async def queue_email(
        self,
        *,
        tenant_id: UUID,
        recipient: str,
        template_code: str,
        subject: str,
        body_text: str,
        body_html: str | None = None,
        recipient_user_id: UUID | None = None,
        idempotency_key: str | None = None,
        metadata: dict | None = None,
    ) -> OutboundMessage:
        key = idempotency_key or hashlib.sha256(
            f"{tenant_id}:{template_code}:{recipient}:{subject}:{body_text}".encode("utf-8")
        ).hexdigest()
        existing = await self.session.scalar(
            select(OutboundMessage).where(
                OutboundMessage.tenant_id == tenant_id,
                OutboundMessage.idempotency_key == key,
            )
        )
        if existing is not None:
            return existing
        message = OutboundMessage(
            id=uuid4(),
            tenant_id=tenant_id,
            channel="email",
            template_code=template_code,
            recipient_address=recipient,
            recipient_user_id=recipient_user_id,
            subject=subject,
            body_text=self.protector.encrypt(body_text),
            body_html=self.protector.encrypt(body_html) if body_html else None,
            status="queued",
            idempotency_key=key,
            scheduled_at=datetime.now(timezone.utc),
            metadata_payload={**(metadata or {}), "body_encrypted": True},
        )
        self.session.add(message)
        await self.session.flush()
        if self.context is not None:
            await AuditService(self.session, self.context).record(
                action="communications.email_queued",
                resource_type="outbound_message",
                resource_id=message.id,
                after_state={"template_code": template_code, "recipient_hash": hashlib.sha256(recipient.lower().encode()).hexdigest()},
            )
        await JobQueueService(self.session).enqueue(
            tenant_id=tenant_id,
            job_type="communications.deliver_email",
            payload={"outbound_message_id": str(message.id)},
            requested_by_user_id=self.context.user_id if self.context else recipient_user_id,
            correlation_id=self.context.correlation_id if self.context else f"message:{message.id}",
            idempotency_key=f"outbound-message:{message.id}",
        )
        return message

    async def deliver(self, message: OutboundMessage) -> OutboundMessage:
        if message.status == "sent":
            return message
        message.attempt_count += 1
        encrypted = bool((message.metadata_payload or {}).get("body_encrypted"))
        body_text = self.protector.decrypt(message.body_text) if encrypted else message.body_text
        body_html = (
            self.protector.decrypt(message.body_html)
            if encrypted and message.body_html
            else message.body_html
        )
        result = await self.gateway.send(
            recipient=message.recipient_address,
            subject=message.subject,
            body_text=body_text,
            body_html=body_html,
        )
        message.provider = result.provider
        message.provider_message_id = result.provider_message_id
        if result.status == "sent":
            message.status = "sent"
            message.sent_at = datetime.now(timezone.utc)
            message.last_error = None
        elif result.status == "blocked":
            message.status = "blocked"
            message.failed_at = datetime.now(timezone.utc)
            message.last_error = result.error
        else:
            message.status = "failed"
            message.failed_at = datetime.now(timezone.utc)
            message.last_error = result.error
        return message
