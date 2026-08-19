from __future__ import annotations

import hashlib
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Query, Request, Response, status
from sqlalchemy import func, or_, select

from ..core.database import set_auth_tenant_context
from ..core.dependencies import AuthenticationDatabaseSession
from ..core.settings import get_settings

from services.database.models import Institution, InstitutionalAccessRequest, PasswordCredential, User

from ..schemas.auth import (
    ContextSelectionRequired,
    DirectPasswordResetRequest,
    DirectRegistrationRequest,
    DirectRegistrationResponse,
    InstitutionalAccessRequestCreate,
    InstitutionalAccessRequestResponse,
    InstitutionSummary,
    InvitationAcceptRequest,
    InvitationAcceptedResponse,
    LoginRequest,
    LogoutRequest,
    RefreshRequest,
    RegistrationRoleOption,
    TokenResponse,
)
from ..services.authentication import AuthenticationService
from ..services.registration import RegistrationService

router = APIRouter(prefix="/auth", tags=["authentication"])


def _request_hashes(request: Request) -> tuple[str | None, str | None]:
    user_agent = request.headers.get("user-agent")
    client_host = request.client.host if request.client else None
    user_agent_hash = hashlib.sha256(user_agent.encode()).hexdigest() if user_agent else None
    source_ip_hash = hashlib.sha256(client_host.encode()).hexdigest() if client_host else None
    return user_agent_hash, source_ip_hash


@router.get("/registration-roles", response_model=list[RegistrationRoleOption])
async def registration_roles(
    session: AuthenticationDatabaseSession,
) -> list[RegistrationRoleOption]:
    """Return role options permitted for direct self-registration.

    Only roles in the DIRECT_REGISTRATION_ALLOWED_ROLES setting are returned.
    institution_administrator and head_of_department are excluded by default
    to prevent privilege escalation through self-service signup.
    """
    return await RegistrationService(session).allowed_roles()


@router.get("/institutions", response_model=list[InstitutionSummary])
async def search_institutions(
    session: AuthenticationDatabaseSession,
    q: str = Query(default="", max_length=200),
) -> list[InstitutionSummary]:
    """Public institution directory — searchable by display name."""
    statement = select(Institution).where(Institution.is_active.is_(True))
    if q.strip():
        term = f"%{q.strip()}%"
        statement = statement.where(
            or_(
                Institution.display_name.ilike(term),
                Institution.slug.ilike(term),
            )
        )
    statement = statement.order_by(Institution.display_name).limit(20)
    institutions = (await session.scalars(statement)).all()
    return [
        InstitutionSummary(
            id=inst.id,
            display_name=inst.display_name,
            institution_type=inst.institution_type,
            country_code=inst.country_code,
        )
        for inst in institutions
    ]


@router.post("/login", response_model=TokenResponse | ContextSelectionRequired)
async def login(
    payload: LoginRequest,
    request: Request,
    session: AuthenticationDatabaseSession,
) -> TokenResponse:
    user_agent_hash, source_ip_hash = _request_hashes(request)
    return await AuthenticationService(session).login(
        payload,
        user_agent_hash=user_agent_hash,
        source_ip_hash=source_ip_hash,
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh(
    payload: RefreshRequest,
    request: Request,
    session: AuthenticationDatabaseSession,
) -> TokenResponse:
    user_agent_hash, source_ip_hash = _request_hashes(request)
    return await AuthenticationService(session).refresh(
        payload,
        user_agent_hash=user_agent_hash,
        source_ip_hash=source_ip_hash,
    )


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    payload: LogoutRequest,
    session: AuthenticationDatabaseSession,
) -> Response:
    if payload.refresh_token is not None:
        await AuthenticationService(session).logout(
            payload.refresh_token.get_secret_value(),
            all_sessions=payload.all_sessions,
        )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/invitations/accept", response_model=InvitationAcceptedResponse)
async def accept_invitation(
    payload: InvitationAcceptRequest,
    session: AuthenticationDatabaseSession,
) -> InvitationAcceptedResponse:
    return await AuthenticationService(session).accept_invitation(payload)


@router.post(
    "/access-requests",
    response_model=InstitutionalAccessRequestResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def request_institutional_access(
    payload: InstitutionalAccessRequestCreate,
    session: AuthenticationDatabaseSession,
) -> InstitutionalAccessRequestResponse:
    """Create a pending request without granting an account or role."""

    institution = await session.scalar(
        select(Institution).where(
            func.lower(Institution.slug) == payload.institution_slug.strip().lower(),
            Institution.is_active.is_(True),
        )
    )
    if institution is None:
        return InstitutionalAccessRequestResponse(
            request_id=uuid4(),
            status="pending",
            message="If the institution accepts access requests, an administrator will review it.",
        )
    await set_auth_tenant_context(session, str(institution.id))
    email = str(payload.email).strip()
    existing = await session.scalar(
        select(InstitutionalAccessRequest).where(
            InstitutionalAccessRequest.tenant_id == institution.id,
            InstitutionalAccessRequest.email_normalized == email.lower(),
            InstitutionalAccessRequest.status.in_(("pending", "needs_information")),
        )
    )
    if existing is None:
        existing = InstitutionalAccessRequest(
            tenant_id=institution.id,
            email=email,
            email_normalized=email.lower(),
            given_name=payload.given_name.strip(),
            family_name=payload.family_name.strip(),
            position_title=payload.position_title.strip() if payload.position_title else None,
            requested_role_code=(
                payload.requested_role_code.strip().lower() if payload.requested_role_code else None
            ),
            request_message=payload.request_message.strip() if payload.request_message else None,
            status="pending",
            metadata_payload={"source": "public_access_request"},
        )
        session.add(existing)
        await session.flush()
    return InstitutionalAccessRequestResponse(
        request_id=existing.id,
        status="pending",
        message="Your request has been submitted for institutional review. No role is granted automatically.",
    )


@router.post(
    "/register",
    response_model=DirectRegistrationResponse,
    status_code=status.HTTP_201_CREATED,
)
async def register(
    payload: DirectRegistrationRequest,
    request: Request,
    session: AuthenticationDatabaseSession,
) -> DirectRegistrationResponse:
    """Self-service account creation.

    Creates user, credential, membership, and role assignment in a single
    transaction, then issues a session token for immediate login.
    """
    user_agent_hash, source_ip_hash = _request_hashes(request)
    return await RegistrationService(session).register(
        payload,
        user_agent_hash=user_agent_hash,
        source_ip_hash=source_ip_hash,
    )


@router.post("/direct-reset", status_code=status.HTTP_204_NO_CONTENT)
async def direct_password_reset(
    payload: DirectPasswordResetRequest,
    session: AuthenticationDatabaseSession,
) -> Response:
    """Staging-only direct password reset — no email link or token required.

    Disabled in production via STAGING_DIRECT_RESET_ENABLED=false (default).
    """
    settings = get_settings()
    if not settings.staging_simple_auth_enabled:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Not found.",
        )

    from ..core.security import PasswordManager
    passwords = PasswordManager(settings)

    email_normalized = str(payload.email).strip().lower()
    user = await session.scalar(
        select(User).where(User.email_normalized == email_normalized)
    )
    if user is None:
        # Neutral response: do not confirm whether the email is registered.
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    from datetime import datetime, timezone
    now = datetime.now(timezone.utc)

    credential = await session.scalar(
        select(PasswordCredential).where(
            PasswordCredential.user_id == user.id
        ).with_for_update()
    )
    if credential is None:
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    try:
        credential.password_hash = passwords.hash(payload.new_password.get_secret_value())
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc

    credential.password_version += 1
    credential.password_changed_at = now
    credential.must_change_password = False
    credential.failed_attempts = 0
    credential.locked_until = None

    return Response(status_code=status.HTTP_204_NO_CONTENT)
