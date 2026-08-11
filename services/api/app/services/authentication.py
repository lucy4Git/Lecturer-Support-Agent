from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

from fastapi import HTTPException, status
from sqlalchemy import and_, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from services.database.models import (
    AccessScope,
    AuthenticationSession,
    Institution,
    InvitationRoleGrant,
    Membership,
    PasswordCredential,
    Role,
    RoleAssignment,
    SecurityEvent,
    User,
    UserInvitation,
)

from ..core.database import set_auth_tenant_context
from ..core.security import PasswordManager, TokenService, parse_invitation_tenant
from ..core.settings import Settings, get_settings
from .account_security import AccountSecurityService

from ..schemas.auth import (
    InvitationAcceptRequest,
    InvitationAcceptedResponse,
    LoginRequest,
    RefreshRequest,
    RoleOption,
    TokenResponse,
)


class AuthenticationService:
    def __init__(self, session: AsyncSession, settings: Settings | None = None) -> None:
        self.session = session
        self.settings = settings or get_settings()
        self.passwords = PasswordManager(self.settings)
        self.tokens = TokenService(self.settings)

    async def login(
        self,
        payload: LoginRequest,
        *,
        user_agent_hash: str | None,
        source_ip_hash: str | None,
    ) -> TokenResponse:
        now = datetime.now(timezone.utc)
        institution = await self._resolve_institution(payload)
        await set_auth_tenant_context(self.session, str(institution.id))
        email_normalized = payload.email.strip().lower()

        user = await self.session.scalar(
            select(User).where(User.email_normalized == email_normalized)
        )
        if user is None or not user.is_active:
            await self._record_security_event(
                tenant_id=institution.id,
                severity="warning",
                event_type="authentication.login_failed",
                description="Login failed for an unknown or inactive account.",
                details={"email_hash": self.tokens.hash_opaque_token(email_normalized)},
                source_ip_hash=source_ip_hash,
            )
            raise self._invalid_credentials()

        membership = await self.session.scalar(
            select(Membership).where(
                Membership.tenant_id == institution.id,
                Membership.user_id == user.id,
            )
        )
        if membership is None or membership.status != "active":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="The institution membership is not active.",
            )

        credential = await self.session.scalar(
            select(PasswordCredential).where(PasswordCredential.user_id == user.id).with_for_update()
        )
        if credential is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="This account must sign in through its configured identity provider.",
            )
        if credential.locked_until and credential.locked_until > now:
            raise HTTPException(
                status_code=status.HTTP_423_LOCKED,
                detail="The account is temporarily locked after repeated failed sign-in attempts.",
            )

        if not self.passwords.verify(payload.password.get_secret_value(), credential.password_hash):
            credential.failed_attempts += 1
            credential.last_failed_at = now
            if credential.failed_attempts >= self.settings.maximum_failed_login_attempts:
                credential.locked_until = now + timedelta(minutes=self.settings.account_lock_minutes)
            await self._record_security_event(
                tenant_id=institution.id,
                severity="warning",
                event_type="authentication.login_failed",
                description="Login failed because the password was not accepted.",
                actor_user_id=user.id,
                source_ip_hash=source_ip_hash,
            )
            raise self._invalid_credentials()

        credential.failed_attempts = 0
        credential.locked_until = None
        role_rows = await self._active_role_options(
            tenant_id=institution.id,
            user_id=user.id,
            now=now,
        )
        if payload.role_code:
            role_rows = [item for item in role_rows if item.role_code == payload.role_code]
        if not role_rows:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="No active role assignment is available for this institution.",
            )
        if len(role_rows) > 1 and not payload.role_code:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "message": "Select the role to use for this session.",
                    "available_roles": [item.model_dump(mode="json") for item in role_rows],
                },
            )

        selected = role_rows[0]
        account_security = AccountSecurityService(self.session, settings=self.settings)
        if await account_security.mfa_required(institution.id, user.id):
            if not payload.mfa_code:
                raise HTTPException(
                    status_code=status.HTTP_428_PRECONDITION_REQUIRED,
                    detail={"message": "A multi-factor authentication code is required.", "code": "mfa_required"},
                )
            if not await account_security.verify_mfa_code(institution.id, user.id, payload.mfa_code):
                await self._record_security_event(
                    tenant_id=institution.id, severity="warning",
                    event_type="authentication.mfa_failed",
                    description="The multi-factor authentication code was not accepted.",
                    actor_user_id=user.id, source_ip_hash=source_ip_hash,
                )
                raise self._invalid_credentials()

        token_response = await self._issue_session(
            tenant_id=institution.id,
            user=user,
            membership=membership,
            role_assignment_id=selected.role_assignment_id,
            role_code=selected.role_code,
            device_label=payload.device_label,
            user_agent_hash=user_agent_hash,
            source_ip_hash=source_ip_hash,
            now=now,
        )
        user.last_login_at = now
        await self._record_security_event(
            tenant_id=institution.id,
            severity="info",
            event_type="authentication.login_succeeded",
            description="User signed in successfully.",
            actor_user_id=user.id,
            source_ip_hash=source_ip_hash,
            details={"role_code": selected.role_code},
        )
        return token_response

    async def refresh(
        self,
        payload: RefreshRequest,
        *,
        user_agent_hash: str | None,
        source_ip_hash: str | None,
    ) -> TokenResponse:
        raw_token = payload.refresh_token.get_secret_value()
        tenant_id, session_id = self.tokens.parse_refresh_token(raw_token)
        await set_auth_tenant_context(self.session, str(tenant_id))
        now = datetime.now(timezone.utc)
        session = await self.session.scalar(
            select(AuthenticationSession)
            .where(
                AuthenticationSession.tenant_id == tenant_id,
                AuthenticationSession.id == session_id,
            )
            .with_for_update()
        )
        if (
            session is None
            or session.refresh_token_hash != self.tokens.hash_opaque_token(raw_token)
            or session.status != "active"
            or session.expires_at <= now
        ):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="The refresh session is invalid, expired, or revoked.",
            )

        membership = await self.session.scalar(
            select(Membership).where(
                Membership.tenant_id == tenant_id,
                Membership.id == session.membership_id,
                Membership.status == "active",
            )
        )
        user = await self.session.scalar(
            select(User).where(User.id == session.user_id, User.is_active.is_(True))
        )
        role_assignment, role = await self._active_role_assignment(
            tenant_id=tenant_id,
            role_assignment_id=session.role_assignment_id,
            now=now,
        )
        if membership is None or user is None or role_assignment is None or role is None:
            session.status = "revoked"
            session.revoked_at = now
            session.revoked_reason = "Authorisation context is no longer active."
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="The account or assigned role is no longer active.",
            )

        session.status = "revoked"
        session.revoked_at = now
        session.revoked_reason = "Refresh token rotated."
        return await self._issue_session(
            tenant_id=tenant_id,
            user=user,
            membership=membership,
            role_assignment_id=role_assignment.id,
            role_code=role.code,
            device_label=session.device_label,
            user_agent_hash=user_agent_hash or session.user_agent_hash,
            source_ip_hash=source_ip_hash,
            now=now,
            rotated_from_session_id=session.id,
        )

    async def logout(self, raw_refresh_token: str, *, all_sessions: bool = False) -> None:
        tenant_id, session_id = self.tokens.parse_refresh_token(raw_refresh_token)
        await set_auth_tenant_context(self.session, str(tenant_id))
        session = await self.session.scalar(
            select(AuthenticationSession).where(
                AuthenticationSession.tenant_id == tenant_id,
                AuthenticationSession.id == session_id,
                AuthenticationSession.refresh_token_hash
                == self.tokens.hash_opaque_token(raw_refresh_token),
            )
        )
        if session is None:
            return
        now = datetime.now(timezone.utc)
        if all_sessions:
            await self.session.execute(
                update(AuthenticationSession)
                .where(
                    AuthenticationSession.tenant_id == tenant_id,
                    AuthenticationSession.user_id == session.user_id,
                    AuthenticationSession.status == "active",
                )
                .values(status="revoked", revoked_at=now, revoked_reason="User signed out all sessions.")
            )
        else:
            session.status = "revoked"
            session.revoked_at = now
            session.revoked_reason = "User signed out."

    async def accept_invitation(
        self,
        payload: InvitationAcceptRequest,
    ) -> InvitationAcceptedResponse:
        raw_token = payload.invitation_token.get_secret_value()
        tenant_id = parse_invitation_tenant(raw_token)
        await set_auth_tenant_context(self.session, str(tenant_id))
        now = datetime.now(timezone.utc)
        invitation = await self.session.scalar(
            select(UserInvitation)
            .where(
                UserInvitation.tenant_id == tenant_id,
                UserInvitation.token_hash == self.tokens.hash_opaque_token(raw_token),
            )
            .with_for_update()
        )
        if invitation is None or invitation.status != "pending":
            raise HTTPException(status_code=400, detail="The invitation is invalid or unavailable.")
        if invitation.expires_at <= now:
            invitation.status = "expired"
            raise HTTPException(status_code=410, detail="The invitation has expired.")

        user = await self.session.scalar(
            select(User).where(User.email_normalized == invitation.email_normalized)
        )
        if user is None:
            user = User(
                id=uuid4(),
                email=invitation.email,
                email_normalized=invitation.email_normalized,
                given_name=payload.given_name.strip(),
                family_name=payload.family_name.strip(),
                display_name=f"{payload.given_name.strip()} {payload.family_name.strip()}".strip(),
                identity_provider="local",
                is_active=True,
            )
            self.session.add(user)
            await self.session.flush()
        elif not user.is_active:
            user.is_active = True

        credential = await self.session.scalar(
            select(PasswordCredential).where(PasswordCredential.user_id == user.id)
        )
        if credential is None:
            credential = PasswordCredential(
                id=uuid4(),
                user_id=user.id,
                password_hash=self.passwords.hash(payload.password.get_secret_value()),
                password_changed_at=now,
            )
            self.session.add(credential)

        membership = await self.session.scalar(
            select(Membership).where(
                Membership.tenant_id == tenant_id,
                Membership.user_id == user.id,
            )
        )
        if membership is None:
            membership = Membership(
                id=uuid4(),
                tenant_id=tenant_id,
                user_id=user.id,
                institutional_identifier=invitation.institutional_identifier,
                position_title=invitation.position_title,
                status="active",
                joined_at=now,
            )
            self.session.add(membership)
            await self.session.flush()
        else:
            membership.status = "active"
            membership.joined_at = membership.joined_at or now
            membership.suspended_at = None
            membership.deactivated_at = None

        grants = (
            await self.session.scalars(
                select(InvitationRoleGrant).where(
                    InvitationRoleGrant.tenant_id == tenant_id,
                    InvitationRoleGrant.invitation_id == invitation.id,
                )
            )
        ).all()
        role_codes: list[str] = []
        for grant in grants:
            role = await self.session.get(Role, grant.role_id)
            if role is None:
                continue
            access_scope = AccessScope(
                id=uuid4(),
                tenant_id=tenant_id,
                scope_type=grant.scope_type,
                scope_id=grant.scope_id,
                include_descendants=grant.include_descendants,
                constraints=grant.constraints,
            )
            self.session.add(access_scope)
            await self.session.flush()
            assignment = RoleAssignment(
                id=uuid4(),
                tenant_id=tenant_id,
                user_id=user.id,
                role_id=role.id,
                access_scope_id=access_scope.id,
                assigned_by_user_id=invitation.invited_by_user_id,
                valid_from=now,
                reason="Assigned through an accepted user invitation.",
            )
            self.session.add(assignment)
            role_codes.append(role.code)

        invitation.status = "accepted"
        invitation.accepted_at = now
        await self._record_security_event(
            tenant_id=tenant_id,
            severity="info",
            event_type="identity.invitation_accepted",
            description="A user invitation was accepted.",
            actor_user_id=user.id,
            details={"invitation_id": str(invitation.id), "role_codes": role_codes},
        )
        return InvitationAcceptedResponse(
            tenant_id=tenant_id,
            user_id=user.id,
            membership_id=membership.id,
            assigned_role_codes=role_codes,
            message="Invitation accepted. Sign in with the institution and an assigned role.",
        )

    async def _resolve_institution(self, payload: LoginRequest) -> Institution:
        if payload.institution_id:
            institution = await self.session.scalar(
                select(Institution).where(
                    Institution.id == payload.institution_id,
                    Institution.is_active.is_(True),
                )
            )
            if institution is None:
                raise HTTPException(status_code=404, detail="Institution was not found or is inactive.")
            return institution

        if payload.institution_slug:
            institution = await self.session.scalar(
                select(Institution).where(
                    Institution.slug == payload.institution_slug,
                    Institution.is_active.is_(True),
                )
            )
            if institution is None:
                raise HTTPException(status_code=404, detail="Institution was not found or is inactive.")
            return institution

        # Email-only login: resolve institution from email domain.
        email_domain = str(payload.email).lower().split("@")[-1]
        domain_matches = (
            await self.session.scalars(
                select(Institution).where(
                    Institution.is_active.is_(True),
                    Institution.configuration["email_domains"].as_string().contains(email_domain),
                )
            )
        ).all()
        if len(domain_matches) == 1:
            return domain_matches[0]

        # Fallback: if exactly one active institution exists, use it.
        all_active = (
            await self.session.scalars(
                select(Institution).where(Institution.is_active.is_(True))
            )
        ).all()
        if len(all_active) == 1:
            return all_active[0]
        if len(all_active) == 0:
            raise HTTPException(status_code=404, detail="No active institutions are registered.")

        # Multiple institutions: return choices to the client.
        from ..schemas.auth import InstitutionSummary
        raise HTTPException(
            status_code=409,
            detail={
                "message": "Your account is associated with multiple institutions. Please select one.",
                "available_institutions": [
                    InstitutionSummary(
                        id=inst.id,
                        display_name=inst.display_name,
                        institution_type=inst.institution_type,
                        country_code=inst.country_code,
                    ).model_dump(mode="json")
                    for inst in all_active
                ],
            },
        )

    async def _active_role_options(
        self,
        *,
        tenant_id: UUID,
        user_id: UUID,
        now: datetime,
    ) -> list[RoleOption]:
        statement = (
            select(RoleAssignment, Role, AccessScope)
            .join(Role, Role.id == RoleAssignment.role_id)
            .outerjoin(AccessScope, AccessScope.id == RoleAssignment.access_scope_id)
            .where(
                RoleAssignment.tenant_id == tenant_id,
                RoleAssignment.user_id == user_id,
                RoleAssignment.valid_from <= now,
                or_(RoleAssignment.valid_until.is_(None), RoleAssignment.valid_until > now),
                RoleAssignment.revoked_at.is_(None),
            )
            .order_by(Role.code)
        )
        rows = (await self.session.execute(statement)).all()
        return [
            RoleOption(
                role_code=role.code,
                role_name=role.name,
                role_assignment_id=assignment.id,
                scope_type=scope.scope_type if scope else None,
                scope_id=scope.scope_id if scope else None,
            )
            for assignment, role, scope in rows
        ]

    async def _active_role_assignment(
        self, *, tenant_id: UUID, role_assignment_id: UUID, now: datetime
    ) -> tuple[RoleAssignment | None, Role | None]:
        row = (
            await self.session.execute(
                select(RoleAssignment, Role)
                .join(Role, Role.id == RoleAssignment.role_id)
                .where(
                    RoleAssignment.tenant_id == tenant_id,
                    RoleAssignment.id == role_assignment_id,
                    RoleAssignment.valid_from <= now,
                    or_(RoleAssignment.valid_until.is_(None), RoleAssignment.valid_until > now),
                    RoleAssignment.revoked_at.is_(None),
                )
            )
        ).one_or_none()
        return row if row else (None, None)

    async def _issue_session(
        self,
        *,
        tenant_id: UUID,
        user: User,
        membership: Membership,
        role_assignment_id: UUID,
        role_code: str,
        device_label: str | None,
        user_agent_hash: str | None,
        source_ip_hash: str | None,
        now: datetime,
        rotated_from_session_id: UUID | None = None,
    ) -> TokenResponse:
        session_id = uuid4()
        refresh_token = self.tokens.build_refresh_token(
            tenant_id=tenant_id,
            session_id=session_id,
        )
        refresh_expires = now + timedelta(days=self.settings.refresh_token_days)
        auth_session = AuthenticationSession(
            id=session_id,
            tenant_id=tenant_id,
            user_id=user.id,
            membership_id=membership.id,
            role_assignment_id=role_assignment_id,
            refresh_token_hash=self.tokens.hash_opaque_token(refresh_token),
            status="active",
            issued_at=now,
            expires_at=refresh_expires,
            last_seen_at=now,
            rotated_from_session_id=rotated_from_session_id,
            device_label=device_label,
            user_agent_hash=user_agent_hash,
            source_ip_hash=source_ip_hash,
        )
        self.session.add(auth_session)
        access_token, access_expires = self.tokens.create_access_token(
            user_id=user.id,
            tenant_id=tenant_id,
            membership_id=membership.id,
            role_assignment_id=role_assignment_id,
            role_code=role_code,
            session_id=session_id,
            now=now,
        )
        return TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            access_token_expires_at=access_expires,
            refresh_token_expires_at=refresh_expires,
            tenant_id=tenant_id,
            user_id=user.id,
            membership_id=membership.id,
            role_assignment_id=role_assignment_id,
            role_code=role_code,
        )

    async def _record_security_event(
        self,
        *,
        tenant_id: UUID,
        severity: str,
        event_type: str,
        description: str,
        actor_user_id: UUID | None = None,
        source_ip_hash: str | None = None,
        details: dict | None = None,
    ) -> None:
        event = SecurityEvent(
            id=uuid4(),
            tenant_id=tenant_id,
            occurred_at=datetime.now(timezone.utc),
            severity=severity,
            event_type=event_type,
            actor_user_id=actor_user_id,
            description=description,
            details={**(details or {}), "source_ip_hash": source_ip_hash},
        )
        self.session.add(event)

    @staticmethod
    def _invalid_credentials() -> HTTPException:
        return HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="The email address or password is incorrect.",
            headers={"WWW-Authenticate": "Bearer"},
        )
