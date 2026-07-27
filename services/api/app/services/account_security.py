from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

from fastapi import HTTPException, status
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from services.database.models import (
    AccountChallenge,
    AuthenticationSession,
    Institution,
    MFADevice,
    MFARecoveryCode,
    Membership,
    PasswordCredential,
    User,
)

from ..core.database import set_auth_tenant_context
from ..core.mfa import MFASecretProtector, TOTP, generate_recovery_codes
from ..core.request_context import RequestContext
from ..core.security import PasswordManager, TokenService
from ..core.settings import Settings, get_settings
from ..schemas.completion import PasswordResetRequest
from .audit import AuditService
from .messaging import MessagingService


class AccountSecurityService:
    def __init__(
        self,
        session: AsyncSession,
        context: RequestContext | None = None,
        settings: Settings | None = None,
    ) -> None:
        self.session = session
        self.context = context
        self.settings = settings or get_settings()
        self.passwords = PasswordManager(self.settings)
        self.tokens = TokenService(self.settings)
        self.totp = TOTP(self.settings)
        self.protector = MFASecretProtector(self.settings)

    @staticmethod
    def _build_token(tenant_id: UUID) -> str:
        return f"{tenant_id}.{secrets.token_urlsafe(48)}"

    @staticmethod
    def _parse_tenant(token: str) -> UUID:
        try:
            return UUID(token.split(".", maxsplit=1)[0])
        except (ValueError, AttributeError, IndexError) as exc:
            raise HTTPException(status_code=400, detail="The account token is malformed.") from exc

    async def request_password_reset(self, payload: PasswordResetRequest, *, source_ip_hash: str | None) -> None:
        institution = await self._resolve_institution(payload.institution_id, payload.institution_slug)
        await set_auth_tenant_context(self.session, str(institution.id))
        user = await self.session.scalar(select(User).where(User.email_normalized == payload.email.strip().lower(), User.is_active.is_(True)))
        if user is None:
            return
        membership = await self.session.scalar(select(Membership).where(Membership.tenant_id == institution.id, Membership.user_id == user.id, Membership.status == "active"))
        if membership is None:
            return
        raw = self._build_token(institution.id)
        now = datetime.now(timezone.utc)
        challenge = AccountChallenge(
            id=uuid4(), tenant_id=institution.id, user_id=user.id,
            challenge_type="password_reset", token_hash=self.tokens.hash_opaque_token(raw),
            status="pending", expires_at=now + timedelta(minutes=self.settings.password_reset_expiry_minutes),
            requested_ip_hash=source_ip_hash,
        )
        self.session.add(challenge)
        await self.session.flush()
        url = f"{self.settings.public_app_url}/reset-password?token={raw}"
        await MessagingService(self.session, settings=self.settings).queue_email(
            tenant_id=institution.id,
            recipient=user.email,
            recipient_user_id=user.id,
            template_code="password_reset",
            subject="Reset your Lecturer Support Agent password",
            body_text=f"A password reset was requested. Use this single-use link before it expires: {url}",
            idempotency_key=f"password-reset:{challenge.id}",
            metadata={"challenge_id": str(challenge.id), "expires_at": challenge.expires_at.isoformat()},
        )

    async def confirm_password_reset(self, raw_token: str, new_password: str) -> None:
        tenant_id = self._parse_tenant(raw_token)
        await set_auth_tenant_context(self.session, str(tenant_id))
        now = datetime.now(timezone.utc)
        challenge = await self.session.scalar(
            select(AccountChallenge).where(
                AccountChallenge.tenant_id == tenant_id,
                AccountChallenge.challenge_type == "password_reset",
                AccountChallenge.token_hash == self.tokens.hash_opaque_token(raw_token),
            ).with_for_update()
        )
        if challenge is None or challenge.status != "pending" or challenge.expires_at <= now or challenge.user_id is None:
            raise HTTPException(status_code=410, detail="The password-reset token is invalid or expired.")
        credential = await self.session.scalar(select(PasswordCredential).where(PasswordCredential.user_id == challenge.user_id).with_for_update())
        if credential is None:
            raise HTTPException(status_code=400, detail="This account does not use a local password.")
        credential.password_hash = self.passwords.hash(new_password)
        credential.password_version += 1
        credential.password_changed_at = now
        credential.failed_attempts = 0
        credential.locked_until = None
        challenge.status = "consumed"
        challenge.consumed_at = now
        await self.session.execute(
            update(AuthenticationSession).where(
                AuthenticationSession.tenant_id == tenant_id,
                AuthenticationSession.user_id == challenge.user_id,
                AuthenticationSession.status == "active",
            ).values(status="revoked", revoked_at=now, revoked_reason="Password reset completed.")
        )

    async def request_email_verification(self) -> None:
        if self.context is None:
            raise RuntimeError("Authenticated context is required.")
        user = await self.session.get(User, self.context.user_id)
        if user is None:
            raise HTTPException(status_code=404, detail="User was not found.")
        raw = self._build_token(self.context.tenant_id)
        challenge = AccountChallenge(
            id=uuid4(), tenant_id=self.context.tenant_id, user_id=user.id,
            challenge_type="email_verification", token_hash=self.tokens.hash_opaque_token(raw),
            status="pending", expires_at=datetime.now(timezone.utc) + timedelta(hours=self.settings.email_verification_expiry_hours),
        )
        self.session.add(challenge)
        await self.session.flush()
        url = f"{self.settings.public_app_url}/verify-email?token={raw}"
        await MessagingService(self.session, self.context, self.settings).queue_email(
            tenant_id=self.context.tenant_id, recipient=user.email, recipient_user_id=user.id,
            template_code="email_verification", subject="Verify your Lecturer Support Agent email",
            body_text=f"Verify your email address using this single-use link: {url}",
            idempotency_key=f"email-verification:{challenge.id}",
        )

    async def confirm_email_verification(self, raw_token: str) -> None:
        tenant_id = self._parse_tenant(raw_token)
        await set_auth_tenant_context(self.session, str(tenant_id))
        now = datetime.now(timezone.utc)
        challenge = await self.session.scalar(select(AccountChallenge).where(
            AccountChallenge.tenant_id == tenant_id,
            AccountChallenge.challenge_type == "email_verification",
            AccountChallenge.token_hash == self.tokens.hash_opaque_token(raw_token),
        ).with_for_update())
        if challenge is None or challenge.status != "pending" or challenge.expires_at <= now or challenge.user_id is None:
            raise HTTPException(status_code=410, detail="The email-verification token is invalid or expired.")
        user = await self.session.get(User, challenge.user_id)
        if user is None:
            raise HTTPException(status_code=404, detail="User was not found.")
        user.profile = {**(user.profile or {}), "email_verified": True, "email_verified_at": now.isoformat()}
        challenge.status = "consumed"; challenge.consumed_at = now

    async def enrol_mfa(self, label: str) -> tuple[MFADevice, str, list[str]]:
        if self.context is None:
            raise RuntimeError("Authenticated context is required.")
        await self.session.execute(update(MFADevice).where(
            MFADevice.tenant_id == self.context.tenant_id,
            MFADevice.user_id == self.context.user_id,
            MFADevice.status == "pending",
        ).values(status="disabled", disabled_at=datetime.now(timezone.utc)))
        secret = self.totp.generate_secret()
        device = MFADevice(
            id=uuid4(), tenant_id=self.context.tenant_id, user_id=self.context.user_id,
            device_type="totp", label=label, secret_ciphertext=self.protector.encrypt(secret), status="pending",
        )
        self.session.add(device); await self.session.flush()
        codes = generate_recovery_codes(self.settings.mfa_recovery_code_count)
        for code in codes:
            self.session.add(MFARecoveryCode(
                id=uuid4(), tenant_id=self.context.tenant_id, device_id=device.id,
                code_hash=self.tokens.hash_opaque_token(code.replace("-", "").upper()),
            ))
        return device, secret, codes

    async def confirm_mfa(self, device_id: UUID, code: str) -> MFADevice:
        if self.context is None:
            raise RuntimeError("Authenticated context is required.")
        device = await self.session.scalar(select(MFADevice).where(
            MFADevice.tenant_id == self.context.tenant_id,
            MFADevice.id == device_id,
            MFADevice.user_id == self.context.user_id,
        ).with_for_update())
        if device is None or device.status != "pending":
            raise HTTPException(status_code=404, detail="Pending MFA enrolment was not found.")
        if not self.totp.verify(self.protector.decrypt(device.secret_ciphertext), code):
            raise HTTPException(status_code=400, detail="The verification code was not accepted.")
        device.status = "active"; device.confirmed_at = datetime.now(timezone.utc)
        return device

    async def disable_mfa(self, device_id: UUID, code: str, reason: str) -> MFADevice:
        if self.context is None:
            raise RuntimeError("Authenticated context is required.")
        device = await self.session.scalar(select(MFADevice).where(
            MFADevice.tenant_id == self.context.tenant_id,
            MFADevice.id == device_id,
            MFADevice.user_id == self.context.user_id,
            MFADevice.status == "active",
        ).with_for_update())
        if device is None:
            raise HTTPException(status_code=404, detail="Active MFA device was not found.")
        if not await self.verify_mfa_code(self.context.tenant_id, self.context.user_id, code, device=device):
            raise HTTPException(status_code=401, detail="The MFA or recovery code was not accepted.")
        device.status = "disabled"; device.disabled_at = datetime.now(timezone.utc)
        await AuditService(self.session, self.context).record(
            action="identity.mfa_disabled", resource_type="mfa_device", resource_id=device.id,
            after_state={"reason": reason},
        )
        return device

    async def verify_mfa_code(self, tenant_id: UUID, user_id: UUID, code: str, *, device: MFADevice | None = None) -> bool:
        device = device or await self.session.scalar(select(MFADevice).where(
            MFADevice.tenant_id == tenant_id,
            MFADevice.user_id == user_id,
            MFADevice.status == "active",
        ).order_by(MFADevice.confirmed_at.desc()))
        if device is None:
            return True
        normalized = code.replace("-", "").upper()
        if self.totp.verify(self.protector.decrypt(device.secret_ciphertext), code):
            device.last_used_at = datetime.now(timezone.utc)
            return True
        recovery = await self.session.scalar(select(MFARecoveryCode).where(
            MFARecoveryCode.tenant_id == tenant_id,
            MFARecoveryCode.device_id == device.id,
            MFARecoveryCode.code_hash == self.tokens.hash_opaque_token(normalized),
            MFARecoveryCode.used_at.is_(None),
        ).with_for_update())
        if recovery is not None:
            recovery.used_at = datetime.now(timezone.utc); device.last_used_at = recovery.used_at
            return True
        return False

    async def mfa_required(self, tenant_id: UUID, user_id: UUID) -> bool:
        return (await self.session.scalar(select(MFADevice.id).where(
            MFADevice.tenant_id == tenant_id,
            MFADevice.user_id == user_id,
            MFADevice.status == "active",
        ).limit(1))) is not None

    async def _resolve_institution(self, institution_id: UUID | None, slug: str | None) -> Institution:
        query = select(Institution).where(Institution.is_active.is_(True))
        query = query.where(Institution.id == institution_id) if institution_id else query.where(Institution.slug == slug)
        institution = await self.session.scalar(query)
        if institution is None:
            raise HTTPException(status_code=404, detail="Institution was not found or is inactive.")
        return institution
