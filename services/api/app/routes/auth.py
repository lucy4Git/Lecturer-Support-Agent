from __future__ import annotations

import hashlib

from fastapi import APIRouter, Request, Response, status

from ..core.dependencies import AuthenticationDatabaseSession
from ..schemas.auth import (
    InvitationAcceptRequest,
    InvitationAcceptedResponse,
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
