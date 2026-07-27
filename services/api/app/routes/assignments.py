from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, status


from ..core.dependencies import CurrentContext, DatabaseSession
from ..schemas.assignments import (
    AssignmentEndRequest,
    CoordinatorAssignmentCreate,
    CoordinatorAssignmentResponse,
    DepartmentTeachingOverview,
    LecturerAssignmentCreate,
    LecturerAssignmentResponse,
    ModeratorAssignmentCreate,
    ModeratorAssignmentResponse,
)
from ..services.assignments import AssignmentService
from ..services.authorization import AuthorizationService

router = APIRouter(prefix="/academic-assignments", tags=["academic assignments"])


@router.post(
    "/lecturers",
    response_model=LecturerAssignmentResponse,
    status_code=status.HTTP_201_CREATED,
)
async def assign_lecturer(
    payload: LecturerAssignmentCreate,
    session: DatabaseSession,
    context: CurrentContext,
) -> LecturerAssignmentResponse:
    await AuthorizationService(session).require_permission(
        tenant_id=context.tenant_id,
        user_id=context.user_id,
        permission_code="academic.assign_lecturer",
        scope_type="module_offering",
        scope_id=payload.module_offering_id,
    )
    assignment = await AssignmentService(session, context).assign_lecturer(
        lecturer_user_id=payload.lecturer_user_id,
        module_offering_id=payload.module_offering_id,
        responsibility_type=payload.responsibility_type,
        workload_percentage=payload.workload_percentage,
        valid_from=payload.valid_from,
        valid_until=payload.valid_until,
    )
    return LecturerAssignmentResponse.model_validate(assignment)


@router.post(
    "/coordinators",
    response_model=CoordinatorAssignmentResponse,
    status_code=status.HTTP_201_CREATED,
)
async def assign_coordinator(
    payload: CoordinatorAssignmentCreate,
    session: DatabaseSession,
    context: CurrentContext,
) -> CoordinatorAssignmentResponse:
    service = AssignmentService(session, context)
    org_unit_id = await service.resolve_target_org_unit(
        target_type=payload.target_type, target_id=payload.target_id
    )
    await AuthorizationService(session).require_permission(
        tenant_id=context.tenant_id,
        user_id=context.user_id,
        permission_code="academic.assign_coordinator",
        scope_type="organisational_unit",
        scope_id=org_unit_id,
    )
    assignment = await service.assign_coordinator(
        user_id=payload.user_id,
        coordinator_type=payload.coordinator_type,
        target_type=payload.target_type,
        target_id=payload.target_id,
        valid_from=payload.valid_from,
        valid_until=payload.valid_until,
    )
    return CoordinatorAssignmentResponse.model_validate(assignment)


@router.post(
    "/moderators",
    response_model=ModeratorAssignmentResponse,
    status_code=status.HTTP_201_CREATED,
)
async def assign_moderator(
    payload: ModeratorAssignmentCreate,
    session: DatabaseSession,
    context: CurrentContext,
) -> ModeratorAssignmentResponse:
    service = AssignmentService(session, context)
    org_unit_id = await service.resolve_target_org_unit(
        target_type=payload.target_type, target_id=payload.target_id
    )
    await AuthorizationService(session).require_permission(
        tenant_id=context.tenant_id,
        user_id=context.user_id,
        permission_code="academic.assign_moderator",
        scope_type="organisational_unit",
        scope_id=org_unit_id,
    )
    assignment = await service.assign_moderator(
        user_id=payload.user_id,
        moderator_type=payload.moderator_type,
        target_type=payload.target_type,
        target_id=payload.target_id,
        valid_from=payload.valid_from,
        valid_until=payload.valid_until,
    )
    return ModeratorAssignmentResponse.model_validate(assignment)


@router.post(
    "/lecturers/{assignment_id}/end",
    response_model=LecturerAssignmentResponse,
)
async def end_lecturer_assignment(
    assignment_id: UUID,
    payload: AssignmentEndRequest,
    session: DatabaseSession,
    context: CurrentContext,
) -> LecturerAssignmentResponse:
    await AuthorizationService(session).require_permission(
        tenant_id=context.tenant_id,
        user_id=context.user_id,
        permission_code="academic.assign_lecturer",
    )
    assignment = await AssignmentService(session, context).end_lecturer_assignment(
        assignment_id,
        reason=payload.reason,
        effective_at=payload.effective_at,
    )
    return LecturerAssignmentResponse.model_validate(assignment)


@router.get(
    "/departments/{organisational_unit_id}/overview",
    response_model=DepartmentTeachingOverview,
)
async def department_overview(
    organisational_unit_id: UUID,
    session: DatabaseSession,
    context: CurrentContext,
) -> DepartmentTeachingOverview:
    await AuthorizationService(session).require_permission(
        tenant_id=context.tenant_id,
        user_id=context.user_id,
        permission_code="department.review",
        scope_type="organisational_unit",
        scope_id=organisational_unit_id,
    )
    return await AssignmentService(session, context).department_overview(
        organisational_unit_id
    )
