from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Query, status
from pydantic import BaseModel, Field

from ..core.dependencies import CurrentContext, DatabaseSession
from ..core.settings import get_settings
from ..schemas.users import (
    MembershipPositionCreate,
    MembershipPositionResponse,
    MembershipStatusUpdate,
    PositionDefinitionCreate,
    PositionDefinitionResponse,
    RoleAssignmentCreate,
    RoleAssignmentResponse,
    UserInvitationCreate,
    UserInvitationResponse,
    UserSummary,
)
from ..services.authorization import AuthorizationService
from ..services.user_administration import UserAdministrationService
from ..services.messaging import MessagingService

router = APIRouter(prefix="/users", tags=["users and roles"])


class RoleRevocationRequest(BaseModel):
    reason: str | None = Field(default=None, max_length=1000)


@router.get("", response_model=list[UserSummary])
async def list_users(
    session: DatabaseSession,
    context: CurrentContext,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> list[UserSummary]:
    await AuthorizationService(session).require_permission(
        tenant_id=context.tenant_id,
        user_id=context.user_id,
        permission_code="users.read",
    )
    return await UserAdministrationService(session, context).list_users(
        limit=limit, offset=offset
    )


@router.post(
    "/invitations",
    response_model=UserInvitationResponse,
    status_code=status.HTTP_201_CREATED,
)
async def invite_user(
    payload: UserInvitationCreate,
    session: DatabaseSession,
    context: CurrentContext,
) -> UserInvitationResponse:
    await AuthorizationService(session).require_permission(
        tenant_id=context.tenant_id,
        user_id=context.user_id,
        permission_code="users.manage",
    )
    invitation, raw_token = await UserAdministrationService(session, context).create_invitation(
        payload
    )
    settings = get_settings()
    acceptance_url = f"{settings.public_app_url}/accept-invitation?token={raw_token}"
    invitation_url = None
    delivery_status = "queued"
    await MessagingService(session, context, settings).queue_email(
        tenant_id=context.tenant_id,
        recipient=invitation.email,
        template_code="user_invitation",
        subject="You have been invited to the Lecturer Support Agent",
        body_text=(
            f"You have been invited to the Lecturer Support Agent. "
            f"Accept the invitation before {invitation.expires_at.isoformat()}: {acceptance_url}"
        ),
        idempotency_key=f"invitation:{invitation.id}",
        metadata={"invitation_id": str(invitation.id), "expires_at": invitation.expires_at.isoformat()},
    )
    if settings.expose_development_invitation_tokens and settings.environment != "production":
        invitation_url = acceptance_url
        delivery_status = "queued_and_development_token_exposed"
    response = UserInvitationResponse.model_validate(invitation)
    return response.model_copy(
        update={"invitation_url": invitation_url, "delivery_status": delivery_status}
    )


@router.patch("/memberships/{membership_id}/status")
async def update_membership_status(
    membership_id: UUID,
    payload: MembershipStatusUpdate,
    session: DatabaseSession,
    context: CurrentContext,
) -> dict:
    await AuthorizationService(session).require_permission(
        tenant_id=context.tenant_id,
        user_id=context.user_id,
        permission_code="users.manage",
    )
    membership = await UserAdministrationService(session, context).update_membership_status(
        membership_id=membership_id, payload=payload
    )
    return {"membership_id": str(membership.id), "status": membership.status}


@router.post(
    "/role-assignments",
    response_model=RoleAssignmentResponse,
    status_code=status.HTTP_201_CREATED,
)
async def assign_role(
    payload: RoleAssignmentCreate,
    session: DatabaseSession,
    context: CurrentContext,
) -> RoleAssignmentResponse:
    await AuthorizationService(session).require_permission(
        tenant_id=context.tenant_id,
        user_id=context.user_id,
        permission_code="roles.assign",
    )
    assignment = await UserAdministrationService(session, context).assign_role(payload)
    return RoleAssignmentResponse.model_validate(assignment)


@router.post(
    "/role-assignments/{role_assignment_id}/revoke",
    response_model=RoleAssignmentResponse,
)
async def revoke_role(
    role_assignment_id: UUID,
    payload: RoleRevocationRequest,
    session: DatabaseSession,
    context: CurrentContext,
) -> RoleAssignmentResponse:
    await AuthorizationService(session).require_permission(
        tenant_id=context.tenant_id,
        user_id=context.user_id,
        permission_code="roles.assign",
    )
    assignment = await UserAdministrationService(session, context).revoke_role(
        role_assignment_id, reason=payload.reason
    )
    return RoleAssignmentResponse.model_validate(assignment)


@router.post(
    "/positions",
    response_model=PositionDefinitionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_position(
    payload: PositionDefinitionCreate,
    session: DatabaseSession,
    context: CurrentContext,
) -> PositionDefinitionResponse:
    await AuthorizationService(session).require_permission(
        tenant_id=context.tenant_id,
        user_id=context.user_id,
        permission_code="positions.manage",
    )
    item = await UserAdministrationService(session, context).create_position_definition(payload)
    return PositionDefinitionResponse.model_validate(item)


@router.post(
    "/membership-positions",
    response_model=MembershipPositionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def assign_position(
    payload: MembershipPositionCreate,
    session: DatabaseSession,
    context: CurrentContext,
) -> MembershipPositionResponse:
    await AuthorizationService(session).require_permission(
        tenant_id=context.tenant_id,
        user_id=context.user_id,
        permission_code="positions.manage",
    )
    item = await UserAdministrationService(session, context).assign_position(payload)
    return MembershipPositionResponse.model_validate(item)
