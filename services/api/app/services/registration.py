"""Direct self-service registration for staging environments.

Creates a User, PasswordCredential, Membership, AccessScope, and RoleAssignment
in a single transaction. The caller is immediately issued a session token.

Gated by STAGING_SIMPLE_AUTH_ENABLED=true. This must never be enabled in
production; the production security validator enforces it.

Name fields (given_name, family_name) are intentionally not collected during
self-registration. The display_name is set to the email local-part as a
staging placeholder — it is not presented as a verified personal name.
Profile information can be collected later through account settings.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from services.database.models import (
    AccessScope,
    AuthenticationSession,
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
from ..schemas.auth import DirectRegistrationRequest, DirectRegistrationResponse, RegistrationRoleOption


class RegistrationService:
    def __init__(self, session: AsyncSession, settings: Settings | None = None) -> None:
        self.session = session
        self.settings = settings or get_settings()
        self.passwords = PasswordManager(self.settings)
        self.tokens = TokenService(self.settings)

    def _allowed_role_codes(self) -> set[str]:
        raw = self.settings.direct_registration_allowed_roles
        return {r.strip().lower() for r in raw.split(",") if r.strip()}

    async def allowed_roles(self) -> list[RegistrationRoleOption]:
        """Return roles permitted for direct registration, ordered by name."""
        allowed = self._allowed_role_codes()
        rows = (
            await self.session.scalars(
                select(Role)
                .where(Role.code.in_(allowed))
                .order_by(Role.name)
            )
        ).all()
        return [RegistrationRoleOption(role_code=r.code, role_name=r.name) for r in rows]

    async def register(
        self,
        payload: DirectRegistrationRequest,
        *,
        user_agent_hash: str | None,
        source_ip_hash: str | None,
    ) -> DirectRegistrationResponse:
        if not self.settings.staging_simple_auth_enabled:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Not found.",
            )

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

        # Validate the submitted email domain against the institution's configured
        # registration-domain policy (fail-closed).
        #
        # Resolution order (most specific wins):
        #   1. registration_role_domains[role_code] — per-role domain list.
        #      Allows institutions to grant different domains per role (e.g. both
        #      tut.ac.za and tut4life.ac.za for Lecturer, but only tut.ac.za for
        #      Module Coordinator). Stored as a JSON object in configuration.
        #   2. staff_email_domains — role-neutral academic domain list.
        #   3. email_domains — legacy flat list (backward compatibility).
        #   4. No domains → fail-closed (registration unavailable).
        email_domain = str(payload.email).strip().lower().rsplit("@", 1)[-1]
        config = institution.configuration or {}
        role_domain_map: dict = config.get("registration_role_domains") or {}
        if role_domain_map and payload.role_code in role_domain_map:
            allowed_domains: list[str] = role_domain_map[payload.role_code] or []
        else:
            allowed_domains = config.get("staff_email_domains") or config.get("email_domains", [])
        if not allowed_domains:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=(
                    "Public self-registration is not currently available for the selected "
                    "institution. Please contact your institution administrator."
                ),
            )
        normalised_domains = {d.strip().lower() for d in allowed_domains if d.strip()}
        if email_domain not in normalised_domains:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Please use an approved institutional email address for the selected institution.",
            )

        # Validate role against the authoritative catalogue and the allow-list.
        allowed_codes = self._allowed_role_codes()
        if payload.role_code not in allowed_codes:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"The role '{payload.role_code}' cannot be self-assigned. "
                    "Privileged roles require an administrator invitation."
                ),
            )
        role = await self.session.scalar(
            select(Role).where(Role.code == payload.role_code)
        )
        if role is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Role '{payload.role_code}' is not recognised in the system catalogue.",
            )

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

        # Derive a non-personal display identifier from the email local-part.
        # This is a staging placeholder, not a verified personal name.
        display_identifier = email_normalized.split("@")[0]

        user_id = uuid4()
        user = User(
            id=user_id,
            email=email,
            email_normalized=email_normalized,
            given_name=None,
            family_name=None,
            display_name=display_identifier,
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
            reason="Self-registered via staging direct registration.",
        )
        self.session.add(assignment)
        await self.session.flush()

        self.session.add(
            SecurityEvent(
                id=uuid4(),
                tenant_id=institution.id,
                occurred_at=now,
                severity="info",
                event_type="identity.direct_registration",
                actor_user_id=user_id,
                description="User self-registered via staging direct registration endpoint.",
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
