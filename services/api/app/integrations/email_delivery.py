from __future__ import annotations

import asyncio
import smtplib
from dataclasses import dataclass
from email.message import EmailMessage
from email.utils import make_msgid

from ..core.settings import Settings, get_settings


@dataclass(frozen=True, slots=True)
class EmailDeliveryResult:
    status: str
    provider: str
    provider_message_id: str | None = None
    error: str | None = None


class EmailGateway:
    async def send(
        self,
        *,
        recipient: str,
        subject: str,
        body_text: str,
        body_html: str | None = None,
    ) -> EmailDeliveryResult:
        raise NotImplementedError


class DisabledEmailGateway(EmailGateway):
    async def send(self, **_: str | None) -> EmailDeliveryResult:
        return EmailDeliveryResult(
            status="blocked",
            provider="disabled",
            error="Email delivery is disabled by configuration.",
        )


class SMTPEmailGateway(EmailGateway):
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()

    async def send(
        self,
        *,
        recipient: str,
        subject: str,
        body_text: str,
        body_html: str | None = None,
    ) -> EmailDeliveryResult:
        return await asyncio.to_thread(
            self._send_sync,
            recipient=recipient,
            subject=subject,
            body_text=body_text,
            body_html=body_html,
        )

    def _send_sync(
        self,
        *,
        recipient: str,
        subject: str,
        body_text: str,
        body_html: str | None,
    ) -> EmailDeliveryResult:
        message = EmailMessage()
        message["From"] = f"{self.settings.email_from_name} <{self.settings.email_from_address}>"
        message["To"] = recipient
        message["Subject"] = subject
        message["Message-ID"] = make_msgid(domain=self.settings.email_from_address.split("@")[-1])
        message.set_content(body_text)
        if body_html:
            message.add_alternative(body_html, subtype="html")
        try:
            smtp_class = smtplib.SMTP_SSL if self.settings.smtp_use_tls else smtplib.SMTP
            with smtp_class(self.settings.smtp_host, self.settings.smtp_port, timeout=30) as client:
                if self.settings.smtp_use_starttls and not self.settings.smtp_use_tls:
                    client.starttls()
                if self.settings.smtp_username:
                    password = self.settings.smtp_password.get_secret_value() if self.settings.smtp_password else ""
                    client.login(self.settings.smtp_username, password)
                refused = client.send_message(message)
                if refused:
                    return EmailDeliveryResult(
                        status="failed",
                        provider="smtp",
                        error="The SMTP server refused one or more recipients.",
                    )
            return EmailDeliveryResult(status="sent", provider="smtp", provider_message_id=message.get("Message-ID"))
        except (OSError, smtplib.SMTPException) as exc:
            return EmailDeliveryResult(status="failed", provider="smtp", error=str(exc)[:1000])


def build_email_gateway(settings: Settings | None = None) -> EmailGateway:
    settings = settings or get_settings()
    if not settings.email_delivery_enabled:
        return DisabledEmailGateway()
    if settings.email_provider != "smtp":
        raise RuntimeError(f"Unsupported email provider: {settings.email_provider}")
    return SMTPEmailGateway(settings)
