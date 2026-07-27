from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID, uuid4

from fastapi import HTTPException
from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from services.database.models import (
    CoordinatorAssignment,
    LecturerAssignment,
    Membership,
    ModeratorAssignment,
    Module,
    ModuleOffering,
    Programme,
)

from ..core.request_context import RequestContext
from ..schemas.assignments import DepartmentTeachingOverview
from .audit import AuditService
from .notifications import NotificationService


class AssignmentService:
    def __init__(self, session: AsyncSession, context: RequestContext) -> None:
        self.session = session
        self.context = context
        self.audit = AuditService(session, context)
        self.notifications = NotificationService(session, context)

    async def assign_lecturer(
        self,
        *,
        lecturer_user_id: UUID,
        module_offering_id: UUID,
        responsibility_type: str,
        workload_percentage: Decimal | None,
        valid_from: datetime,
        valid_until: datetime | None,
    ) -> LecturerAssignment:
        await self._require_active_member(lecturer_user_id)
        await self._require_module_offering(module_offering_id)
        existing = (
            await self.session.scalars(
                select(LecturerAssignment)
                .where(
                    LecturerAssignment.tenant_id == self.context.tenant_id,
                    LecturerAssignment.user_id == lecturer_user_id,
                    LecturerAssignment.module_offering_id == module_offering_id,
                    LecturerAssignment.status == "active",
                )
                .with_for_update()
            )
        ).all()
        now = datetime.now(timezone.utc)
        for assignment in existing:
            end_candidates = [value for value in (assignment.valid_until, valid_from) if value]
            assignment.valid_until = min(end_candidates)
            assignment.status = "ended" if assignment.valid_until <= now else "active"
            assignment.ended_reason = "Superseded by a new authorised assignment."

        assignment = LecturerAssignment(
            id=uuid4(),
            tenant_id=self.context.tenant_id,
            user_id=lecturer_user_id,
            module_offering_id=module_offering_id,
            assigned_by_user_id=self.context.user_id,
            responsibility_type=responsibility_type,
            workload_percentage=workload_percentage,
            status="active",
            valid_from=valid_from,
            valid_until=valid_until,
        )
        self.session.add(assignment)
        await self.session.flush()
        await self.audit.record(
            action="academic.lecturer_assigned",
            resource_type="lecturer_assignment",
            resource_id=assignment.id,
            after_state={
                "lecturer_user_id": str(lecturer_user_id),
                "module_offering_id": str(module_offering_id),
                "responsibility_type": responsibility_type,
                "workload_percentage": (
                    str(workload_percentage) if workload_percentage is not None else None
                ),
            },
        )
        await self.notifications.emit(
            recipient_user_id=lecturer_user_id,
            notification_type="module_assignment",
            title="New module assignment",
            body="You have been assigned to a module offering. Review the teaching context, plan, readiness requirements, and upcoming dates in the unified work area.",
            action_path="action:teachingPlan",
            resource_type="lecturer_assignment",
            resource_id=assignment.id,
            metadata={"module_offering_id": str(module_offering_id)},
        )
        return assignment

    async def assign_coordinator(
        self,
        *,
        user_id: UUID,
        coordinator_type: str,
        target_type: str,
        target_id: UUID,
        valid_from: datetime,
        valid_until: datetime | None,
    ) -> CoordinatorAssignment:
        await self._require_active_member(user_id)
        await self.resolve_target_org_unit(target_type=target_type, target_id=target_id)
        await self._end_matching_coordinator_assignments(
            coordinator_type=coordinator_type,
            target_type=target_type,
            target_id=target_id,
            effective_at=valid_from,
        )
        assignment = CoordinatorAssignment(
            id=uuid4(),
            tenant_id=self.context.tenant_id,
            user_id=user_id,
            coordinator_type=coordinator_type,
            target_type=target_type,
            target_id=target_id,
            assigned_by_user_id=self.context.user_id,
            valid_from=valid_from,
            valid_until=valid_until,
            status="active",
        )
        self.session.add(assignment)
        await self.session.flush()
        await self.audit.record(
            action="academic.coordinator_assigned",
            resource_type="coordinator_assignment",
            resource_id=assignment.id,
            after_state={
                "user_id": str(user_id),
                "coordinator_type": coordinator_type,
                "target_type": target_type,
                "target_id": str(target_id),
            },
        )
        await self.notifications.emit(
            recipient_user_id=user_id,
            notification_type="coordination_assignment",
            title="New coordination responsibility",
            body="A coordination responsibility has been assigned to you. Review its scope and current teaching operations.",
            action_path="action:operationsDashboard",
            resource_type="coordinator_assignment",
            resource_id=assignment.id,
            metadata={"target_type": target_type, "target_id": str(target_id)},
        )
        return assignment

    async def assign_moderator(
        self,
        *,
        user_id: UUID,
        moderator_type: str,
        target_type: str,
        target_id: UUID,
        valid_from: datetime,
        valid_until: datetime | None,
    ) -> ModeratorAssignment:
        await self._require_active_member(user_id)
        assignment = ModeratorAssignment(
            id=uuid4(),
            tenant_id=self.context.tenant_id,
            user_id=user_id,
            moderator_type=moderator_type,
            target_type=target_type,
            target_id=target_id,
            assigned_by_user_id=self.context.user_id,
            valid_from=valid_from,
            valid_until=valid_until,
            status="active",
        )
        self.session.add(assignment)
        await self.session.flush()
        await self.audit.record(
            action="academic.moderator_assigned",
            resource_type="moderator_assignment",
            resource_id=assignment.id,
            after_state={
                "user_id": str(user_id),
                "moderator_type": moderator_type,
                "target_type": target_type,
                "target_id": str(target_id),
            },
        )
        await self.notifications.emit(
            recipient_user_id=user_id,
            notification_type="moderation_assignment",
            title="Moderation responsibility assigned",
            body="You have been assigned a moderation responsibility. Exact review tasks and evidence will appear when the review cycle is created.",
            action_path="action:reviewTasks",
            resource_type="moderator_assignment",
            resource_id=assignment.id,
            metadata={"target_type": target_type, "target_id": str(target_id)},
        )
        return assignment

    async def end_lecturer_assignment(
        self, assignment_id: UUID, *, reason: str, effective_at: datetime | None
    ) -> LecturerAssignment:
        assignment = await self.session.scalar(
            select(LecturerAssignment)
            .where(
                LecturerAssignment.tenant_id == self.context.tenant_id,
                LecturerAssignment.id == assignment_id,
            )
            .with_for_update()
        )
        if assignment is None:
            raise HTTPException(status_code=404, detail="Lecturer assignment was not found.")
        assignment.status = "ended"
        assignment.valid_until = effective_at or datetime.now(timezone.utc)
        assignment.ended_reason = reason
        await self.audit.record(
            action="academic.lecturer_assignment_ended",
            resource_type="lecturer_assignment",
            resource_id=assignment.id,
            after_state={"reason": reason, "effective_at": assignment.valid_until.isoformat()},
        )
        return assignment

    async def department_overview(self, organisational_unit_id: UUID) -> DepartmentTeachingOverview:
        now = datetime.now(timezone.utc)
        offerings = (
            await self.session.scalars(
                select(ModuleOffering.id).where(
                    ModuleOffering.tenant_id == self.context.tenant_id,
                    ModuleOffering.org_unit_id == organisational_unit_id,
                    or_(ModuleOffering.ends_on.is_(None), ModuleOffering.ends_on >= now.date()),
                )
            )
        ).all()
        offering_ids = list(offerings)
        if not offering_ids:
            return DepartmentTeachingOverview(
                organisational_unit_id=organisational_unit_id,
                active_module_offerings=0,
                active_lecturer_assignments=0,
                unassigned_module_offerings=0,
                active_coordinator_assignments=0,
                active_moderator_assignments=0,
                total_allocated_workload_percentage=Decimal("0"),
            )
        lecturer_rows = (
            await self.session.execute(
                select(
                    LecturerAssignment.module_offering_id,
                    LecturerAssignment.workload_percentage,
                ).where(
                    LecturerAssignment.tenant_id == self.context.tenant_id,
                    LecturerAssignment.module_offering_id.in_(offering_ids),
                    LecturerAssignment.status == "active",
                    LecturerAssignment.valid_from <= now,
                    or_(
                        LecturerAssignment.valid_until.is_(None),
                        LecturerAssignment.valid_until > now,
                    ),
                )
            )
        ).all()
        assigned_offerings = {row.module_offering_id for row in lecturer_rows}
        workload = sum(
            (row.workload_percentage or Decimal("0") for row in lecturer_rows),
            Decimal("0"),
        )
        coordinator_count = await self.session.scalar(
            select(func.count(CoordinatorAssignment.id)).where(
                CoordinatorAssignment.tenant_id == self.context.tenant_id,
                CoordinatorAssignment.status == "active",
                or_(
                    and_(
                        CoordinatorAssignment.target_type == "module_offering",
                        CoordinatorAssignment.target_id.in_(offering_ids),
                    ),
                    and_(
                        CoordinatorAssignment.target_type == "organisational_unit",
                        CoordinatorAssignment.target_id == organisational_unit_id,
                    ),
                ),
            )
        )
        moderator_count = await self.session.scalar(
            select(func.count(ModeratorAssignment.id)).where(
                ModeratorAssignment.tenant_id == self.context.tenant_id,
                ModeratorAssignment.status == "active",
                ModeratorAssignment.target_type == "module_offering",
                ModeratorAssignment.target_id.in_(offering_ids),
            )
        )
        return DepartmentTeachingOverview(
            organisational_unit_id=organisational_unit_id,
            active_module_offerings=len(offering_ids),
            active_lecturer_assignments=len(lecturer_rows),
            unassigned_module_offerings=len(set(offering_ids) - assigned_offerings),
            active_coordinator_assignments=int(coordinator_count or 0),
            active_moderator_assignments=int(moderator_count or 0),
            total_allocated_workload_percentage=workload,
        )

    async def resolve_target_org_unit(self, *, target_type: str, target_id: UUID) -> UUID:
        if target_type == "module_offering":
            value = await self.session.scalar(
                select(ModuleOffering.org_unit_id).where(
                    ModuleOffering.tenant_id == self.context.tenant_id,
                    ModuleOffering.id == target_id,
                )
            )
        elif target_type == "module":
            value = await self.session.scalar(
                select(Module.owning_unit_id).where(
                    Module.tenant_id == self.context.tenant_id,
                    Module.id == target_id,
                )
            )
        elif target_type == "programme":
            value = await self.session.scalar(
                select(Programme.owning_unit_id).where(
                    Programme.tenant_id == self.context.tenant_id,
                    Programme.id == target_id,
                )
            )
        elif target_type == "organisational_unit":
            value = target_id
        else:
            raise HTTPException(status_code=400, detail="Unsupported academic assignment target.")
        if value is None:
            raise HTTPException(status_code=404, detail="Academic assignment target was not found.")
        return value

    async def _require_active_member(self, user_id: UUID) -> None:
        found = await self.session.scalar(
            select(Membership.id).where(
                Membership.tenant_id == self.context.tenant_id,
                Membership.user_id == user_id,
                Membership.status == "active",
            )
        )
        if found is None:
            raise HTTPException(status_code=404, detail="The assigned user is not an active member.")

    async def _require_module_offering(self, module_offering_id: UUID) -> None:
        found = await self.session.scalar(
            select(ModuleOffering.id).where(
                ModuleOffering.tenant_id == self.context.tenant_id,
                ModuleOffering.id == module_offering_id,
            )
        )
        if found is None:
            raise HTTPException(status_code=404, detail="Module offering was not found.")

    async def _end_matching_coordinator_assignments(
        self,
        *,
        coordinator_type: str,
        target_type: str,
        target_id: UUID,
        effective_at: datetime,
    ) -> None:
        current = (
            await self.session.scalars(
                select(CoordinatorAssignment)
                .where(
                    CoordinatorAssignment.tenant_id == self.context.tenant_id,
                    CoordinatorAssignment.coordinator_type == coordinator_type,
                    CoordinatorAssignment.target_type == target_type,
                    CoordinatorAssignment.target_id == target_id,
                    CoordinatorAssignment.status == "active",
                )
                .with_for_update()
            )
        ).all()
        for item in current:
            item.status = "ended"
            item.valid_until = effective_at
