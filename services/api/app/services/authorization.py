from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from services.database.models import (
    AccessScope,
    Membership,
    Permission,
    Role,
    RoleAssignment,
    RolePermission,
)

from ..core.request_context import RequestContext, get_request_context


class AuthorizationService:
    """Database-backed active-role and scope checks.

    A session is authorised only through the role assignment selected at login.
    Holding another role does not silently add its permissions to the active
    session. Institution Administrator and Head of Department therefore remain
    operationally independent even when one person holds both assignments.
    """

    def __init__(
        self,
        session: AsyncSession,
        context: RequestContext | None = None,
    ) -> None:
        self.session = session
        self.context = context or get_request_context()

    async def has_permission(
        self,
        *,
        tenant_id: UUID,
        user_id: UUID,
        permission_code: str,
        scope_type: str | None = None,
        scope_id: UUID | None = None,
    ) -> bool:
        if tenant_id != self.context.tenant_id or user_id != self.context.user_id:
            return False
        now = datetime.now(timezone.utc)
        statement = (
            select(
                RoleAssignment.id,
                AccessScope.scope_type,
                AccessScope.scope_id,
                AccessScope.include_descendants,
            )
            .join(Role, Role.id == RoleAssignment.role_id)
            .join(RolePermission, RolePermission.role_id == Role.id)
            .join(Permission, Permission.id == RolePermission.permission_id)
            .join(
                Membership,
                (Membership.tenant_id == RoleAssignment.tenant_id)
                & (Membership.user_id == RoleAssignment.user_id),
            )
            .outerjoin(AccessScope, AccessScope.id == RoleAssignment.access_scope_id)
            .where(
                RoleAssignment.tenant_id == tenant_id,
                RoleAssignment.user_id == user_id,
                Role.code == self.context.role_code,
                Permission.code == permission_code,
                Membership.status == "active",
                RoleAssignment.valid_from <= now,
                or_(RoleAssignment.valid_until.is_(None), RoleAssignment.valid_until > now),
                RoleAssignment.revoked_at.is_(None),
            )
        )
        if self.context.role_assignment_id is not None:
            statement = statement.where(RoleAssignment.id == self.context.role_assignment_id)
        rows = (await self.session.execute(statement)).all()
        if scope_type is None:
            return bool(rows)
        for _, assignment_scope_type, assignment_scope_id, include_descendants in rows:
            if assignment_scope_type in {None, "institution"}:
                return True
            if assignment_scope_type == scope_type and assignment_scope_id == scope_id:
                return True
            if include_descendants and assignment_scope_type == "organisational_unit":
                requested_org_unit = await self._resolve_org_unit(
                    tenant_id=tenant_id,
                    scope_type=scope_type,
                    scope_id=scope_id,
                )
                if await self._is_descendant(
                    tenant_id,
                    assignment_scope_id,
                    requested_org_unit,
                ):
                    return True
        return False

    async def _resolve_org_unit(
        self, *, tenant_id: UUID, scope_type: str, scope_id: UUID | None
    ) -> UUID | None:
        if scope_id is None:
            return None
        if scope_type == "organisational_unit":
            return scope_id
        from services.database.models import Module, ModuleOffering, Programme

        if scope_type == "module":
            return await self.session.scalar(
                select(Module.owning_unit_id).where(
                    Module.tenant_id == tenant_id,
                    Module.id == scope_id,
                )
            )
        if scope_type == "programme":
            return await self.session.scalar(
                select(Programme.owning_unit_id).where(
                    Programme.tenant_id == tenant_id,
                    Programme.id == scope_id,
                )
            )
        if scope_type == "module_offering":
            return await self.session.scalar(
                select(ModuleOffering.org_unit_id).where(
                    ModuleOffering.tenant_id == tenant_id,
                    ModuleOffering.id == scope_id,
                )
            )
        return None

    async def _is_descendant(
        self,
        tenant_id: UUID,
        ancestor_id: UUID | None,
        descendant_id: UUID | None,
    ) -> bool:
        if ancestor_id is None or descendant_id is None:
            return False
        from services.database.models import OrganisationalUnitClosure

        statement = select(OrganisationalUnitClosure.depth).where(
            OrganisationalUnitClosure.tenant_id == tenant_id,
            OrganisationalUnitClosure.ancestor_id == ancestor_id,
            OrganisationalUnitClosure.descendant_id == descendant_id,
        )
        return (await self.session.scalar(statement)) is not None

    async def require_permission(self, **kwargs: object) -> None:
        if not await self.has_permission(**kwargs):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="The active role and scope do not permit this action.",
            )
