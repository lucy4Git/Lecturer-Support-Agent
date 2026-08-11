"""Direct self-service registration for staging environments.

Creates a User, PasswordCredential, Membership, AccessScope, and RoleAssignment
in a single transaction. The caller is immediately issued a session token.

This endpoint must not be enabled in production. Production onboarding goes
through the invitation workflow (InstitutionAdministrator sends invitation,
user accepts with a signed token).
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from services.database.models import (
    AccessScope,
    Institution,
    Membership,
    PasswordCredential,
    Role,
    RoleAssignment,
    SecurityEvent,
    User,
)

from ..core.database import set_auth_tenant_context
from ..core.security import PasswordManager, TokenService
from ..core.settings import Settings, get_settings
from ..schemas.auth import DirectRegistrationRequest, DirectRegistrationResponse


class RegistrationService:
    def __init__(self, session: AsyncSession, settings: Settings | None = None) -> None:
        self.session = session
        self.settings = settings or get_settings()
        self.passwords = PasswordManager(self.settings)
        self.tokens = TokenService(self.settings)

    async def register(
        self,
        payload: DirectRegistrationRequest,
        *,
        user_agent_hash: str | None,
        source_ip_hash: str | None,
    ) -> DirectRegistrationResponse:
        now = datetime.now(timezone.utc)

        institution = await self.session.scalar(
            select(Institution).where(
                Institution.id == payload.institution_id,
                Institution.is_active.is_(True),
            )
        )
        if institution is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="The selected institution was not found or is inactive.",
            )

        await set_auth_tenant_context(self.session, str(institution.id))

        email = str(payload.email).strip()
        email_normalized = email.lower()

        existing_user = await self.session.scalar(
            select(User).where(User.email_normalized == email_normalized)
        )
        if existing_user is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="An account with this email address already exists.",
            )

        role = await self.session.scalar(
            select(Role).where(Role.code == payload.role_code)
        )
        if role is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Role '{payload.role_code}' is not recognised.",
            )

        user_id = uuid4()
        user = User(
            id=user_id,
            email=email,
            email_normalized=email_normalized,
            given_name=payload.given_name.strip(),
            family_name=payload.family_name.strip(),
            display_name=f"{payload.given_name.strip()} {payload.family_name.strip()}".strip(),
            identity_provider="local",
            is_active=True,
        )
        self.session.add(user)
        await self.session.flush()

        credential = PasswordCredential(
            id=uuid4(),
            user_id=user_id,
            password_hash=self.passwords.hash(payload.password.get_secret_value()),
            password_changed_at=now,
        )
        self.session.add(credential)

        membership_id = uuid4()
        membership = Membership(
            id=membership_id,
            tenant_id=institution.id,
            user_id=user_id,
            status="active",
            joined_at=now,
        )
        self.session.add(membership)
        await self.session.flush()

        scope_id = uuid4()
        access_scope = AccessScope(
            id=scope_id,
            tenant_id=institution.id,
            scope_type="institution",
            scope_id=None,
            include_descendants=True,
            constraints={},
        )
        self.session.add(access_scope)
        await self.session.flush()

        assignment_id = uuid4()
        assignment = RoleAssignment(
            id=assignment_id,
            tenant_id=institution.id,
            user_id=user_id,
            role_id=role.id,
            access_scope_id=scope_id,
            assigned_by_user_id=user_id,
            valid_from=now,
            reason="Self-registered via direct registration.",
        )
        self.session.add(assignment)

        self.session.add(
            SecurityEvent(
                id=uuid4(),
                tenant_id=institution.id,
                occurred_at=now,
                severity="info",
                event_type="identity.direct_registration",
                actor_user_id=user_id,
                description="User self-registered via direct registration endpoint.",
                details={
                    "role_code": payload.role_code,
                    "source_ip_hash": source_ip_hash,
                },
            )
        )

        session_id = uuid4()
        refresh_token = self.tokens.build_refresh_token(
            tenant_id=institution.id,
            session_id=session_id,
        )
        refresh_expires = now + timedelta(days=self.settings.refresh_token_days)

        from services.database.models import AuthenticationSession
        auth_session = AuthenticationSession(
            id=session_id,
            tenant_id=institution.id,
            user_id=user_id,
            membership_id=membership_id,
            role_assignment_id=assignment_id,
            refresh_token_hash=self.tokens.hash_opaque_token(refresh_token),
            status="active",
            issued_at=now,
            expires_at=refresh_expires,
            last_seen_at=now,
            device_label=None,
            user_agent_hash=user_agent_hash,
            source_ip_hash=source_ip_hash,
        )
        self.session.add(auth_session)

        access_token, access_expires = self.tokens.create_access_token(
            user_id=user_id,
            tenant_id=institution.id,
            membership_id=membership_id,
            role_assignment_id=assignment_id,
            role_code=payload.role_code,
            session_id=session_id,
            now=now,
        )

        return DirectRegistrationResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            access_token_expires_at=access_expires,
            refresh_token_expires_at=refresh_expires,
            tenant_id=institution.id,
            user_id=user_id,
            membership_id=membership_id,
            role_assignment_id=assignment_id,
            role_code=payload.role_code,
            message="Account created. Welcome to the Lecturer Support Agent.",
        )
