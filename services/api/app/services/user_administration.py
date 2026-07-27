from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

from fastapi import HTTPException, status
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from services.database.models import (
    AccessScope,
    InvitationRoleGrant,
    Membership,
    MembershipPosition,
    PositionDefinition,
    Role,
    RoleAssignment,
    UserInvitation,
)

from ..core.request_context import RequestContext
from ..core.security import TokenService, build_invitation_token
from ..core.settings import Settings, get_settings
from ..schemas.users import (
    MembershipPositionCreate,
    MembershipStatusUpdate,
    PositionDefinitionCreate,
    RoleAssignmentCreate,
    UserInvitationCreate,
    UserSummary,
)
from .audit import AuditService


class UserAdministrationService:
    def __init__(
        self,
        session: AsyncSession,
        context: RequestContext,
        settings: Settings | None = None,
    ) -> None:
        self.session = session
        self.context = context
        self.settings = settings or get_settings()
        self.audit = AuditService(session, context)

    async def list_users(self, *, limit: int = 100, offset: int = 0) -> list[UserSummary]:
        rows = (
            await self.session.execute(
                text(
                    """
                    SELECT user_id, membership_id, email, display_name,
                           institutional_identifier, position_title,
                           membership_status, is_active, created_at
                    FROM iam.current_tenant_users
                    ORDER BY display_name, email
                    LIMIT :limit OFFSET :offset
                    """
                ),
                {"limit": limit, "offset": offset},
            )
        ).mappings()
        return [UserSummary.model_validate(dict(row)) for row in rows]

    async def create_invitation(
        self,
        payload: UserInvitationCreate,
    ) -> tuple[UserInvitation, str]:
        now = datetime.now(timezone.utc)
        email_normalized = payload.email.strip().lower()
        pending = await self.session.scalar(
            select(UserInvitation).where(
                UserInvitation.tenant_id == self.context.tenant_id,
                UserInvitation.email_normalized == email_normalized,
                UserInvitation.status == "pending",
                UserInvitation.expires_at > now,
            )
        )
        if pending is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="An active invitation already exists for this email address.",
            )

        roles = (
            await self.session.scalars(
                select(Role).where(Role.code.in_({item.role_code for item in payload.roles}))
            )
        ).all()
        role_by_code = {item.code: item for item in roles}
        missing = sorted({item.role_code for item in payload.roles} - set(role_by_code))
        if missing:
            raise HTTPException(
                status_code=400,
                detail={"message": "Unknown roles in invitation.", "role_codes": missing},
            )

        raw_token = build_invitation_token(self.context.tenant_id)
        invitation = UserInvitation(
            id=uuid4(),
            tenant_id=self.context.tenant_id,
            email=str(payload.email),
            email_normalized=email_normalized,
            invited_by_user_id=self.context.user_id,
            token_hash=TokenService.hash_opaque_token(raw_token),
            status="pending",
            expires_at=now + timedelta(hours=self.settings.invitation_expiry_hours),
            institutional_identifier=payload.institutional_identifier,
            position_title=payload.position_title,
            invitation_message=payload.invitation_message,
        )
        self.session.add(invitation)
        await self.session.flush()
        for requested in payload.roles:
            self.session.add(
                InvitationRoleGrant(
                    id=uuid4(),
                    tenant_id=self.context.tenant_id,
                    invitation_id=invitation.id,
                    role_id=role_by_code[requested.role_code].id,
                    scope_type=requested.scope_type,
                    scope_id=requested.scope_id,
                    include_descendants=requested.include_descendants,
                    constraints=requested.constraints,
                )
            )
        await self.audit.record(
            action="identity.user_invited",
            resource_type="user_invitation",
            resource_id=invitation.id,
            after_state={
                "email_hash": TokenService.hash_opaque_token(email_normalized),
                "role_codes": [item.role_code for item in payload.roles],
                "expires_at": invitation.expires_at.isoformat(),
            },
        )
        return invitation, raw_token

    async def update_membership_status(
        self,
        *,
        membership_id: UUID,
        payload: MembershipStatusUpdate,
    ) -> Membership:
        membership = await self.session.scalar(
            select(Membership)
            .where(
                Membership.tenant_id == self.context.tenant_id,
                Membership.id == membership_id,
            )
            .with_for_update()
        )
        if membership is None:
            raise HTTPException(status_code=404, detail="Membership was not found.")
        before = {"status": membership.status}
        now = datetime.now(timezone.utc)
        membership.status = payload.status
        if payload.status == "active":
            membership.joined_at = membership.joined_at or now
            membership.suspended_at = None
            membership.deactivated_at = None
            membership.deactivation_reason = None
        elif payload.status == "suspended":
            membership.suspended_at = now
            membership.deactivation_reason = payload.reason
        else:
            membership.deactivated_at = now
            membership.deactivation_reason = payload.reason
        await self.audit.record(
            action=f"identity.membership_{payload.status}",
            resource_type="membership",
            resource_id=membership.id,
            before_state=before,
            after_state={"status": membership.status, "reason": payload.reason},
        )
        return membership

    async def assign_role(self, payload: RoleAssignmentCreate) -> RoleAssignment:
        membership = await self.session.scalar(
            select(Membership).where(
                Membership.tenant_id == self.context.tenant_id,
                Membership.user_id == payload.user_id,
            )
        )
        if membership is None:
            raise HTTPException(status_code=404, detail="The user is not a member of this institution.")
        role = await self.session.scalar(select(Role).where(Role.code == payload.role_code))
        if role is None:
            raise HTTPException(status_code=404, detail="Role was not found.")

        scope = AccessScope(
            id=uuid4(),
            tenant_id=self.context.tenant_id,
            scope_type=payload.scope_type,
            scope_id=payload.scope_id,
            include_descendants=payload.include_descendants,
        )
        self.session.add(scope)
        await self.session.flush()
        assignment = RoleAssignment(
            id=uuid4(),
            tenant_id=self.context.tenant_id,
            user_id=payload.user_id,
            role_id=role.id,
            access_scope_id=scope.id,
            assigned_by_user_id=self.context.user_id,
            valid_from=payload.valid_from,
            valid_until=payload.valid_until,
            reason=payload.reason,
        )
        self.session.add(assignment)
        await self.session.flush()
        await self.audit.record(
            action="identity.role_assigned",
            resource_type="role_assignment",
            resource_id=assignment.id,
            after_state={
                "user_id": str(payload.user_id),
                "role_code": role.code,
                "scope_type": payload.scope_type,
                "scope_id": str(payload.scope_id) if payload.scope_id else None,
            },
        )
        return assignment

    async def revoke_role(self, role_assignment_id: UUID, *, reason: str | None) -> RoleAssignment:
        assignment = await self.session.scalar(
            select(RoleAssignment)
            .where(
                RoleAssignment.tenant_id == self.context.tenant_id,
                RoleAssignment.id == role_assignment_id,
            )
            .with_for_update()
        )
        if assignment is None:
            raise HTTPException(status_code=404, detail="Role assignment was not found.")
        if assignment.revoked_at is None:
            assignment.revoked_at = datetime.now(timezone.utc)
            assignment.revoked_by_user_id = self.context.user_id
            assignment.reason = reason or assignment.reason
        await self.audit.record(
            action="identity.role_revoked",
            resource_type="role_assignment",
            resource_id=assignment.id,
            after_state={"reason": reason},
        )
        return assignment

    async def create_position_definition(
        self, payload: PositionDefinitionCreate
    ) -> PositionDefinition:
        existing = await self.session.scalar(
            select(PositionDefinition).where(
                PositionDefinition.tenant_id == self.context.tenant_id,
                PositionDefinition.code == payload.code,
            )
        )
        if existing:
            raise HTTPException(status_code=409, detail="Position code already exists.")
        position = PositionDefinition(
            id=uuid4(),
            tenant_id=self.context.tenant_id,
            code=payload.code,
            label=payload.label,
            category=payload.category,
            description=payload.description,
            attributes=payload.attributes,
        )
        self.session.add(position)
        await self.session.flush()
        await self.audit.record(
            action="identity.position_created",
            resource_type="position_definition",
            resource_id=position.id,
            after_state={"code": position.code, "label": position.label},
        )
        return position

    async def assign_position(self, payload: MembershipPositionCreate) -> MembershipPosition:
        membership = await self.session.scalar(
            select(Membership).where(
                Membership.tenant_id == self.context.tenant_id,
                Membership.id == payload.membership_id,
            )
        )
        position = await self.session.scalar(
            select(PositionDefinition).where(
                PositionDefinition.tenant_id == self.context.tenant_id,
                PositionDefinition.id == payload.position_definition_id,
                PositionDefinition.is_active.is_(True),
            )
        )
        if membership is None or position is None:
            raise HTTPException(status_code=404, detail="Membership or position was not found.")
        if payload.is_primary:
            current_primary = (
                await self.session.scalars(
                    select(MembershipPosition).where(
                        MembershipPosition.tenant_id == self.context.tenant_id,
                        MembershipPosition.membership_id == payload.membership_id,
                        MembershipPosition.is_primary.is_(True),
                        MembershipPosition.valid_until.is_(None),
                    )
                )
            ).all()
            for item in current_primary:
                item.is_primary = False
        assignment = MembershipPosition(
            id=uuid4(),
            tenant_id=self.context.tenant_id,
            membership_id=payload.membership_id,
            position_definition_id=payload.position_definition_id,
            organisational_unit_id=payload.organisational_unit_id,
            assigned_by_user_id=self.context.user_id,
            is_primary=payload.is_primary,
            valid_from=payload.valid_from,
            valid_until=payload.valid_until,
        )
        self.session.add(assignment)
        await self.session.flush()
        await self.audit.record(
            action="identity.position_assigned",
            resource_type="membership_position",
            resource_id=assignment.id,
            after_state={
                "membership_id": str(payload.membership_id),
                "position_code": position.code,
                "organisational_unit_id": (
                    str(payload.organisational_unit_id) if payload.organisational_unit_id else None
                ),
            },
        )
        return assignment
