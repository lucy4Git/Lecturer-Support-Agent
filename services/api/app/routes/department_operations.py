from __future__ import annotations

from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Query, status

from ..core.dependencies import CurrentContext, DatabaseSession
from ..schemas.department_operations import (
    CalendarEventCreate, CalendarEventRead, CalendarEventStatusUpdate, DepartmentOperationsDashboard,
    HandoverCreate, HandoverRead, HandoverTransition, HandoverVersionCreate, HandoverVersionRead,
    ReadinessItemCreate, ReadinessItemRead, ReadinessItemUpdate, ReadinessProfileCreate, ReadinessProfileRead,
    TeachingPlanCreate, TeachingPlanRead, TeachingPlanStatusUpdate, TeachingPlanVersionCreate, TeachingPlanVersionRead,
    TeachingSessionCreate, TeachingSessionRead, TeachingSessionStatusUpdate,
    WorkloadActivityCreate, WorkloadActivityEnd, WorkloadActivityRead, WorkloadSummary,
)
from ..services.department_operations import DepartmentOperationsService

router=APIRouter(prefix="/department-operations", tags=["departmental teaching operations"])

@router.post("/calendar/events", response_model=CalendarEventRead, status_code=status.HTTP_201_CREATED)
async def create_calendar_event(payload: CalendarEventCreate, session: DatabaseSession, context: CurrentContext):
    return CalendarEventRead.model_validate(await DepartmentOperationsService(session, context).create_calendar_event(payload))

@router.get("/calendar/events", response_model=list[CalendarEventRead])
async def list_calendar_events(session: DatabaseSession, context: CurrentContext, organisational_unit_id: UUID|None=None, starts_from: datetime|None=None, starts_before: datetime|None=None):
    return [CalendarEventRead.model_validate(x) for x in await DepartmentOperationsService(session, context).list_calendar_events(organisational_unit_id=organisational_unit_id, starts_from=starts_from, starts_before=starts_before)]

@router.post("/calendar/events/{event_id}/status", response_model=CalendarEventRead)
async def transition_calendar_event(event_id: UUID, payload: CalendarEventStatusUpdate, session: DatabaseSession, context: CurrentContext):
    return CalendarEventRead.model_validate(await DepartmentOperationsService(session, context).transition_calendar_event(event_id, payload))

@router.post("/teaching-plans", response_model=TeachingPlanRead, status_code=status.HTTP_201_CREATED)
async def create_teaching_plan(payload: TeachingPlanCreate, session: DatabaseSession, context: CurrentContext):
    plan,_=await DepartmentOperationsService(session, context).create_teaching_plan(payload); return TeachingPlanRead.model_validate(plan)

@router.get("/teaching-plans", response_model=list[TeachingPlanRead])
async def list_teaching_plans(session: DatabaseSession, context: CurrentContext, module_offering_id: UUID|None=None):
    return [TeachingPlanRead.model_validate(x) for x in await DepartmentOperationsService(session, context).list_teaching_plans(module_offering_id)]

@router.post("/teaching-plans/{plan_id}/status", response_model=TeachingPlanRead)
async def transition_teaching_plan(plan_id: UUID, payload: TeachingPlanStatusUpdate, session: DatabaseSession, context: CurrentContext):
    return TeachingPlanRead.model_validate(await DepartmentOperationsService(session, context).transition_teaching_plan(plan_id, payload))

@router.post("/teaching-plans/{plan_id}/versions", response_model=TeachingPlanVersionRead, status_code=status.HTTP_201_CREATED)
async def create_teaching_plan_version(plan_id: UUID, payload: TeachingPlanVersionCreate, session: DatabaseSession, context: CurrentContext):
    return TeachingPlanVersionRead.model_validate(await DepartmentOperationsService(session, context).create_plan_version(plan_id, payload))

@router.get("/teaching-plans/{plan_id}/sessions", response_model=list[TeachingSessionRead])
async def list_teaching_sessions(plan_id: UUID, session: DatabaseSession, context: CurrentContext):
    return [TeachingSessionRead.model_validate(x) for x in await DepartmentOperationsService(session, context).list_teaching_sessions(plan_id)]

@router.post("/teaching-plans/{plan_id}/sessions", response_model=TeachingSessionRead, status_code=status.HTTP_201_CREATED)
async def create_teaching_session(plan_id: UUID, payload: TeachingSessionCreate, session: DatabaseSession, context: CurrentContext):
    return TeachingSessionRead.model_validate(await DepartmentOperationsService(session, context).create_teaching_session(plan_id, payload))

@router.post("/teaching-sessions/{session_id}/status", response_model=TeachingSessionRead)
async def transition_teaching_session(session_id: UUID, payload: TeachingSessionStatusUpdate, session: DatabaseSession, context: CurrentContext):
    return TeachingSessionRead.model_validate(await DepartmentOperationsService(session, context).transition_teaching_session(session_id, payload))

@router.get("/readiness/profiles", response_model=list[ReadinessProfileRead])
async def list_readiness_profiles(session: DatabaseSession, context: CurrentContext, module_offering_id: UUID|None=None):
    return [ReadinessProfileRead.model_validate(x) for x in await DepartmentOperationsService(session, context).list_readiness_profiles(module_offering_id)]

@router.get("/readiness/profiles/{profile_id}/items", response_model=list[ReadinessItemRead])
async def list_readiness_items(profile_id: UUID, session: DatabaseSession, context: CurrentContext):
    return [ReadinessItemRead.model_validate(x) for x in await DepartmentOperationsService(session, context).list_readiness_items(profile_id)]

@router.post("/readiness/profiles", response_model=ReadinessProfileRead, status_code=status.HTTP_201_CREATED)
async def create_readiness_profile(payload: ReadinessProfileCreate, session: DatabaseSession, context: CurrentContext):
    return ReadinessProfileRead.model_validate(await DepartmentOperationsService(session, context).create_readiness_profile(payload))

@router.post("/readiness/profiles/{profile_id}/items", response_model=ReadinessItemRead, status_code=status.HTTP_201_CREATED)
async def add_readiness_item(profile_id: UUID, payload: ReadinessItemCreate, session: DatabaseSession, context: CurrentContext):
    return ReadinessItemRead.model_validate(await DepartmentOperationsService(session, context).add_readiness_item(profile_id, payload))

@router.patch("/readiness/items/{item_id}", response_model=ReadinessItemRead)
async def update_readiness_item(item_id: UUID, payload: ReadinessItemUpdate, session: DatabaseSession, context: CurrentContext):
    return ReadinessItemRead.model_validate(await DepartmentOperationsService(session, context).update_readiness_item(item_id, payload))

@router.post("/readiness/profiles/{profile_id}/evaluate", response_model=ReadinessProfileRead)
async def evaluate_readiness(profile_id: UUID, session: DatabaseSession, context: CurrentContext):
    return ReadinessProfileRead.model_validate(await DepartmentOperationsService(session, context).evaluate_readiness(profile_id))

@router.post("/workloads/activities", response_model=WorkloadActivityRead, status_code=status.HTTP_201_CREATED)
async def create_workload_activity(payload: WorkloadActivityCreate, session: DatabaseSession, context: CurrentContext):
    return WorkloadActivityRead.model_validate(await DepartmentOperationsService(session, context).create_workload_activity(payload))

@router.post("/workloads/activities/{activity_id}/end", response_model=WorkloadActivityRead)
async def end_workload_activity(activity_id: UUID, payload: WorkloadActivityEnd, session: DatabaseSession, context: CurrentContext):
    return WorkloadActivityRead.model_validate(await DepartmentOperationsService(session, context).end_workload_activity(activity_id, payload))

@router.get("/workloads/{user_id}", response_model=WorkloadSummary)
async def workload_summary(user_id: UUID, session: DatabaseSession, context: CurrentContext, academic_period_id: UUID=Query(...)):
    return await DepartmentOperationsService(session, context).workload_summary(user_id, academic_period_id)

@router.post("/handovers", response_model=HandoverRead, status_code=status.HTTP_201_CREATED)
async def create_handover(payload: HandoverCreate, session: DatabaseSession, context: CurrentContext):
    package,_=await DepartmentOperationsService(session, context).create_handover(payload); return HandoverRead.model_validate(package)

@router.get("/handovers", response_model=list[HandoverRead])
async def list_handovers(session: DatabaseSession, context: CurrentContext, module_offering_id: UUID|None=None):
    return [HandoverRead.model_validate(x) for x in await DepartmentOperationsService(session, context).list_handovers(module_offering_id)]

@router.get("/handovers/{package_id}/versions", response_model=list[HandoverVersionRead])
async def list_handover_versions(package_id: UUID, session: DatabaseSession, context: CurrentContext):
    return [HandoverVersionRead.model_validate(x) for x in await DepartmentOperationsService(session, context).list_handover_versions(package_id)]

@router.post("/handovers/{package_id}/versions", response_model=HandoverVersionRead, status_code=status.HTTP_201_CREATED)
async def create_handover_version(package_id: UUID, payload: HandoverVersionCreate, session: DatabaseSession, context: CurrentContext):
    return HandoverVersionRead.model_validate(await DepartmentOperationsService(session, context).create_handover_version(package_id, payload))

@router.post("/handovers/{package_id}/transition", response_model=HandoverRead)
async def transition_handover(package_id: UUID, payload: HandoverTransition, session: DatabaseSession, context: CurrentContext):
    package,_=await DepartmentOperationsService(session, context).transition_handover(package_id, payload); return HandoverRead.model_validate(package)

@router.get("/dashboards/departments/{organisational_unit_id}", response_model=DepartmentOperationsDashboard)
async def department_operations_dashboard(organisational_unit_id: UUID, session: DatabaseSession, context: CurrentContext):
    return await DepartmentOperationsService(session, context).dashboard(organisational_unit_id)
