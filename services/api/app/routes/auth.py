from __future__ import annotations

import hashlib
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Request, Response, status

from ..core.database import set_auth_tenant_context
from ..core.dependencies import AuthenticationDatabaseSession
from sqlalchemy import func, select

from services.database.models import Institution, InstitutionalAccessRequest

from ..schemas.auth import (
    InvitationAcceptRequest,
    InvitationAcceptedResponse,
    InstitutionalAccessRequestCreate,
    InstitutionalAccessRequestResponse,
    LoginRequest,
    LogoutRequest,
    RefreshRequest,
    TokenResponse,
)
from ..services.authentication import AuthenticationService

router = APIRouter(prefix="/auth", tags=["authentication"])


def _request_hashes(request: Request) -> tuple[str | None, str | None]:
    user_agent = request.headers.get("user-agent")
    client_host = request.client.host if request.client else None
    user_agent_hash = hashlib.sha256(user_agent.encode()).hexdigest() if user_agent else None
    source_ip_hash = hashlib.sha256(client_host.encode()).hexdigest() if client_host else None
    return user_agent_hash, source_ip_hash


@router.post("/login", response_model=TokenResponse)
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
    # Return a neutral message for unknown institutions to prevent enumeration.
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
