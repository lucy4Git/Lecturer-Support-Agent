from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, status

from ..core.dependencies import CurrentContext, DatabaseSession
from ..schemas.external_access import (
    ExternalAccessGrantCreate,
    ExternalAccessGrantResponse,
    ExternalAccessRevoke,
)
from ..services.authorization import AuthorizationService
from ..services.external_access import ExternalAccessService

router = APIRouter(prefix="/external-access", tags=["external access"])


@router.post(
    "/grants",
    response_model=ExternalAccessGrantResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_external_grant(
    payload: ExternalAccessGrantCreate,
    session: DatabaseSession,
    context: CurrentContext,
) -> ExternalAccessGrantResponse:
    await AuthorizationService(session).require_permission(
        tenant_id=context.tenant_id,
        user_id=context.user_id,
        permission_code="external_access.manage",
    )
    grant = await ExternalAccessService(session, context).create_grant(
        external_user_id=payload.external_user_id,
        purpose=payload.purpose,
        starts_at=payload.starts_at,
        expires_at=payload.expires_at,
        allowed_actions=payload.allowed_actions,
        resource_scope=payload.resource_scope,
    )
    return ExternalAccessGrantResponse.model_validate(grant)


@router.post("/grants/{grant_id}/revoke", response_model=ExternalAccessGrantResponse)
async def revoke_external_grant(
    grant_id: UUID,
    payload: ExternalAccessRevoke,
    session: DatabaseSession,
    context: CurrentContext,
) -> ExternalAccessGrantResponse:
    await AuthorizationService(session).require_permission(
        tenant_id=context.tenant_id,
        user_id=context.user_id,
        permission_code="external_access.manage",
    )
    row = await ExternalAccessService(session, context).revoke_grant(grant_id, payload.reason)
    return ExternalAccessGrantResponse.model_validate(row)


@router.post("/expire-due")
async def expire_due_external_grants(
    session: DatabaseSession,
    context: CurrentContext,
) -> dict[str, int]:
    await AuthorizationService(session).require_permission(
        tenant_id=context.tenant_id,
        user_id=context.user_id,
        permission_code="external_access.manage",
    )
    return {"expired": await ExternalAccessService(session, context).expire_due_grants()}
