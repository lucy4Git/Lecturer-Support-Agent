from __future__ import annotations

import hashlib
import json
from datetime import date, datetime, timezone
from decimal import Decimal
from uuid import UUID, uuid4

from fastapi import HTTPException, status
from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from services.database.models import (
    AcademicCalendarEvent,
    AcademicPeriod,
    HandoverAction,
    HandoverPackage,
    HandoverVersion,
    LecturerAssignment,
    ModuleOffering,
    ModuleReadinessItem,
    ModuleReadinessProfile,
    OperationalAlert,
    TeachingPlan,
    TeachingPlanVersion,
    TeachingSession,
    TeachingWorkload,
    WorkloadActivity,
)
from services.database.models.enums import (
    HandoverStatus,
    ModuleReadinessStatus,
    ReadinessItemStatus,
    TeachingSessionStatus,
)

from ..core.request_context import RequestContext
from ..schemas.department_operations import DepartmentOperationsDashboard, WorkloadSummary
from .audit import AuditService
from .authorization import AuthorizationService


def canonical_checksum(payload: dict) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode()).hexdigest()


class TeachingPlanStateMachine:
    TRANSITIONS = {
        ("draft", "activate"): "active",
        ("active", "pause"): "paused",
        ("paused", "activate"): "active",
        ("active", "complete"): "completed",
        ("completed", "archive"): "archived",
        ("draft", "archive"): "archived",
    }

    @classmethod
    def transition(cls, current: str, action: str) -> str:
        try:
            return cls.TRANSITIONS[(current, action)]
        except KeyError as exc:
            raise ValueError(f"Invalid teaching-plan transition: {current} -> {action}") from exc


class TeachingSessionStateMachine:
    TRANSITIONS = {
        ("planned", "deliver"): "delivered",
        ("planned", "reschedule"): "rescheduled",
        ("planned", "cancel"): "cancelled",
        ("planned", "mark_missed"): "missed",
        ("rescheduled", "deliver"): "delivered",
        ("rescheduled", "reschedule"): "rescheduled",
        ("rescheduled", "cancel"): "cancelled",
        ("rescheduled", "mark_missed"): "missed",
    }

    @classmethod
    def transition(cls, current: str, action: str) -> str:
        try:
            return cls.TRANSITIONS[(current, action)]
        except KeyError as exc:
            raise ValueError(f"Invalid teaching-session transition: {current} -> {action}") from exc


class HandoverStateMachine:
    TRANSITIONS = {
        ("draft", "submit"): "submitted",
        ("changes_requested", "submit"): "submitted",
        ("submitted", "request_changes"): "changes_requested",
        ("submitted", "accept"): "accepted",
        ("accepted", "complete"): "completed",
        ("completed", "archive"): "archived",
    }

    @classmethod
    def transition(cls, current: str, action: str) -> str:
        try:
            return cls.TRANSITIONS[(current, action)]
        except KeyError as exc:
            raise ValueError(f"Invalid handover transition: {current} -> {action}") from exc


class ReadinessCalculator:
    COMPLETED = {ReadinessItemStatus.COMPLETE.value, ReadinessItemStatus.WAIVED.value, ReadinessItemStatus.NOT_APPLICABLE.value}

    @classmethod
    def calculate(cls, items: list[dict]) -> tuple[Decimal, str, int]:
        applicable = [item for item in items if item.get("status") != ReadinessItemStatus.NOT_APPLICABLE.value]
        total = sum((Decimal(str(item.get("weight", 1))) for item in applicable), Decimal("0"))
        complete = sum((Decimal(str(item.get("weight", 1))) for item in applicable if item.get("status") in cls.COMPLETED), Decimal("0"))
        score = (complete / total * Decimal("100")) if total else Decimal("100")
        score = score.quantize(Decimal("0.01"))
        blocking = sum(1 for item in applicable if item.get("blocking") and item.get("status") not in cls.COMPLETED)
        if blocking:
            state = ModuleReadinessStatus.BLOCKED.value
        elif score == Decimal("100.00"):
            state = ModuleReadinessStatus.READY.value
        elif score >= Decimal("60"):
            state = ModuleReadinessStatus.PARTIALLY_READY.value
        elif applicable:
            state = ModuleReadinessStatus.AT_RISK.value
        else:
            state = ModuleReadinessStatus.NOT_STARTED.value
        return score, state, blocking


class WorkloadCalculator:
    @staticmethod
    def summarise(activities: list[tuple[Decimal, Decimal]], limit: Decimal | None) -> tuple[Decimal, Decimal, Decimal | None, bool]:
        raw = sum((hours for hours, _ in activities), Decimal("0"))
        weighted = sum((hours * factor for hours, factor in activities), Decimal("0"))
        utilisation = None if not limit or limit <= 0 else (weighted / limit * Decimal("100")).quantize(Decimal("0.01"))
        return raw, weighted, utilisation, bool(utilisation is not None and utilisation > 100)


class DepartmentOperationsService:
    def __init__(self, session: AsyncSession, context: RequestContext) -> None:
        self.session = session
        self.context = context
        self.audit = AuditService(session, context)
        self.authorization = AuthorizationService(session, context)

    async def _offering(self, offering_id: UUID, permission: str | None = None) -> ModuleOffering:
        offering = await self.session.scalar(select(ModuleOffering).where(ModuleOffering.tenant_id == self.context.tenant_id, ModuleOffering.id == offering_id))
        if offering is None:
            raise HTTPException(status_code=404, detail="Module offering was not found.")
        if permission:
            await self.authorization.require_permission(tenant_id=self.context.tenant_id, user_id=self.context.user_id, permission_code=permission, scope_type="module_offering", scope_id=offering_id)
        if self.context.role_code == "lecturer" and permission in {"teaching_plans.read", "teaching_plans.manage", "module_readiness.read", "module_readiness.manage", "handover.read", "handover.manage"}:
            now = datetime.now(timezone.utc)
            assignment = await self.session.scalar(
                select(LecturerAssignment.id).where(
                    LecturerAssignment.tenant_id == self.context.tenant_id,
                    LecturerAssignment.user_id == self.context.user_id,
                    LecturerAssignment.module_offering_id == offering_id,
                    LecturerAssignment.status == "active",
                    LecturerAssignment.valid_from <= now,
                    or_(LecturerAssignment.valid_until.is_(None), LecturerAssignment.valid_until > now),
                )
            )
            if assignment is None:
                raise HTTPException(status_code=403, detail="The lecturer is not actively assigned to this module offering.")
        return offering

    async def create_calendar_event(self, payload) -> AcademicCalendarEvent:
        scope_id = payload.organisational_unit_id
        if payload.module_offering_id:
            offering = await self._offering(payload.module_offering_id)
            scope_id = scope_id or offering.org_unit_id
        await self.authorization.require_permission(tenant_id=self.context.tenant_id, user_id=self.context.user_id, permission_code="academic_calendar.manage", scope_type="organisational_unit" if scope_id else None, scope_id=scope_id)
        event = AcademicCalendarEvent(id=uuid4(), tenant_id=self.context.tenant_id, academic_period_id=payload.academic_period_id, organisational_unit_id=scope_id, module_offering_id=payload.module_offering_id, created_by_user_id=self.context.user_id, event_type=payload.event_type, title=payload.title, description=payload.description, starts_at=payload.starts_at, ends_at=payload.ends_at, all_day=payload.all_day, visibility=payload.visibility, recurrence_rule=payload.recurrence_rule, event_metadata=payload.metadata)
        self.session.add(event); await self.session.flush()
        await self.audit.record(action="operations.calendar_event_created", resource_type="academic_calendar_event", resource_id=event.id, after_state={"title": event.title, "starts_at": event.starts_at.isoformat()})
        return event

    async def list_calendar_events(self, *, organisational_unit_id: UUID | None, starts_from: datetime | None, starts_before: datetime | None) -> list[AcademicCalendarEvent]:
        await self.authorization.require_permission(tenant_id=self.context.tenant_id, user_id=self.context.user_id, permission_code="academic_calendar.read", scope_type="organisational_unit" if organisational_unit_id else None, scope_id=organisational_unit_id)
        q=select(AcademicCalendarEvent).where(AcademicCalendarEvent.tenant_id == self.context.tenant_id)
        if organisational_unit_id: q=q.where(or_(AcademicCalendarEvent.organisational_unit_id == organisational_unit_id, AcademicCalendarEvent.organisational_unit_id.is_(None)))
        if starts_from: q=q.where(AcademicCalendarEvent.starts_at >= starts_from)
        if starts_before: q=q.where(AcademicCalendarEvent.starts_at < starts_before)
        return list(await self.session.scalars(q.order_by(AcademicCalendarEvent.starts_at).limit(500)))

    async def transition_calendar_event(self, event_id: UUID, payload) -> AcademicCalendarEvent:
        event = await self.session.scalar(select(AcademicCalendarEvent).where(AcademicCalendarEvent.tenant_id == self.context.tenant_id, AcademicCalendarEvent.id == event_id).with_for_update())
        if event is None:
            raise HTTPException(status_code=404, detail="Academic calendar event was not found.")
        scope_id = event.organisational_unit_id
        if scope_id is None and event.module_offering_id is not None:
            offering = await self._offering(event.module_offering_id)
            scope_id = offering.org_unit_id
        await self.authorization.require_permission(tenant_id=self.context.tenant_id, user_id=self.context.user_id, permission_code="academic_calendar.manage", scope_type="organisational_unit" if scope_id else None, scope_id=scope_id)
        allowed = {("scheduled", "complete"): "completed", ("scheduled", "cancel"): "cancelled"}
        before = event.status
        try:
            event.status = allowed[(before, payload.action)]
        except KeyError as exc:
            raise HTTPException(status_code=409, detail=f"Invalid calendar transition: {before} -> {payload.action}") from exc
        await self.audit.record(action="operations.calendar_event_status_changed", resource_type="academic_calendar_event", resource_id=event.id, before_state={"status": before}, after_state={"status": event.status, "reason": payload.reason})
        return event

    async def create_teaching_plan(self, payload) -> tuple[TeachingPlan, TeachingPlanVersion]:
        offering = await self._offering(payload.module_offering_id, "teaching_plans.manage")
        plan=TeachingPlan(id=uuid4(), tenant_id=self.context.tenant_id, module_offering_id=offering.id, academic_period_id=offering.academic_period_id, owner_user_id=self.context.user_id, title=payload.title, planned_contact_hours=payload.planned_contact_hours, starts_on=payload.starts_on, ends_on=payload.ends_on)
        self.session.add(plan); await self.session.flush()
        version=await self._new_plan_version(plan, change_reason="Initial teaching plan", summary=payload.summary, weekly_schedule=payload.weekly_schedule, learning_outcome_mapping=payload.learning_outcome_mapping, assessment_milestones=payload.assessment_milestones, resource_requirements=payload.resource_requirements)
        await self.audit.record(action="operations.teaching_plan_created", resource_type="teaching_plan", resource_id=plan.id, after_state={"module_offering_id": str(offering.id), "version": 1})
        return plan, version

    async def _new_plan_version(self, plan: TeachingPlan, **values) -> TeachingPlanVersion:
        current=await self.session.scalar(select(TeachingPlanVersion).where(TeachingPlanVersion.tenant_id == self.context.tenant_id, TeachingPlanVersion.teaching_plan_id == plan.id, TeachingPlanVersion.is_current.is_(True)).with_for_update())
        if current: current.is_current=False
        number=(current.version_number+1) if current else 1
        payload={k: values[k] for k in ("summary","weekly_schedule","learning_outcome_mapping","assessment_milestones","resource_requirements")}
        version=TeachingPlanVersion(id=uuid4(), tenant_id=self.context.tenant_id, teaching_plan_id=plan.id, version_number=number, previous_version_id=current.id if current else None, created_by_user_id=self.context.user_id, change_reason=values["change_reason"], checksum_sha256=canonical_checksum(payload), is_current=True, **payload)
        self.session.add(version); await self.session.flush(); plan.current_version_id=version.id
        return version

    async def create_plan_version(self, plan_id: UUID, payload) -> TeachingPlanVersion:
        plan=await self.session.scalar(select(TeachingPlan).where(TeachingPlan.tenant_id == self.context.tenant_id, TeachingPlan.id == plan_id).with_for_update())
        if not plan: raise HTTPException(status_code=404, detail="Teaching plan was not found.")
        await self._offering(plan.module_offering_id, "teaching_plans.manage")
        version=await self._new_plan_version(plan, **payload.model_dump())
        await self.audit.record(action="operations.teaching_plan_version_created", resource_type="teaching_plan", resource_id=plan.id, after_state={"version": version.version_number, "checksum": version.checksum_sha256})
        return version

    async def list_teaching_plans(self, offering_id: UUID | None) -> list[TeachingPlan]:
        if offering_id: await self._offering(offering_id, "teaching_plans.read")
        else: await self.authorization.require_permission(tenant_id=self.context.tenant_id, user_id=self.context.user_id, permission_code="teaching_plans.read")
        q=select(TeachingPlan).where(TeachingPlan.tenant_id == self.context.tenant_id)
        if offering_id: q=q.where(TeachingPlan.module_offering_id == offering_id)
        if self.context.role_code == "lecturer": q=q.where(TeachingPlan.owner_user_id == self.context.user_id)
        return list(await self.session.scalars(q.order_by(TeachingPlan.updated_at.desc()).limit(300)))

    async def transition_teaching_plan(self, plan_id: UUID, payload) -> TeachingPlan:
        plan = await self.session.scalar(select(TeachingPlan).where(TeachingPlan.tenant_id == self.context.tenant_id, TeachingPlan.id == plan_id).with_for_update())
        if plan is None:
            raise HTTPException(status_code=404, detail="Teaching plan was not found.")
        await self._offering(plan.module_offering_id, "teaching_plans.manage")
        before = plan.status
        try:
            plan.status = TeachingPlanStateMachine.transition(before, payload.action)
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        await self.audit.record(action="operations.teaching_plan_status_changed", resource_type="teaching_plan", resource_id=plan.id, before_state={"status": before}, after_state={"status": plan.status, "reason": payload.reason})
        return plan

    async def list_teaching_sessions(self, plan_id: UUID) -> list[TeachingSession]:
        plan = await self.session.scalar(select(TeachingPlan).where(TeachingPlan.tenant_id == self.context.tenant_id, TeachingPlan.id == plan_id))
        if plan is None:
            raise HTTPException(status_code=404, detail="Teaching plan was not found.")
        await self._offering(plan.module_offering_id, "teaching_plans.read")
        return list(await self.session.scalars(select(TeachingSession).where(TeachingSession.tenant_id == self.context.tenant_id, TeachingSession.teaching_plan_id == plan_id).order_by(TeachingSession.planned_start)))

    async def create_teaching_session(self, plan_id: UUID, payload) -> TeachingSession:
        plan=await self.session.scalar(select(TeachingPlan).where(TeachingPlan.tenant_id == self.context.tenant_id, TeachingPlan.id == plan_id))
        if not plan: raise HTTPException(status_code=404, detail="Teaching plan was not found.")
        await self._offering(plan.module_offering_id, "teaching_plans.manage")
        row=TeachingSession(id=uuid4(), tenant_id=self.context.tenant_id, teaching_plan_id=plan.id, module_offering_id=plan.module_offering_id, topic=payload.topic, session_type=payload.session_type, planned_start=payload.planned_start, planned_end=payload.planned_end, learning_outcome_ids=[str(x) for x in payload.learning_outcome_ids], notes=payload.notes)
        self.session.add(row); await self.session.flush()
        await self.audit.record(action="operations.teaching_session_planned", resource_type="teaching_session", resource_id=row.id, after_state={"topic": row.topic, "planned_start": row.planned_start.isoformat()})
        return row

    async def transition_teaching_session(self, session_id: UUID, payload) -> TeachingSession:
        row=await self.session.scalar(select(TeachingSession).where(TeachingSession.tenant_id == self.context.tenant_id, TeachingSession.id == session_id).with_for_update())
        if not row: raise HTTPException(status_code=404, detail="Teaching session was not found.")
        await self._offering(row.module_offering_id, "teaching_plans.manage")
        before=row.status
        try: row.status=TeachingSessionStateMachine.transition(row.status, payload.action)
        except ValueError as exc: raise HTTPException(status_code=409, detail=str(exc)) from exc
        if row.status == TeachingSessionStatus.DELIVERED.value:
            row.actual_start=payload.actual_start or row.planned_start; row.actual_end=payload.actual_end or row.planned_end; row.delivered_by_user_id=self.context.user_id
        row.evidence_document_version_ids=[str(x) for x in payload.evidence_document_version_ids]; row.attendance_summary=payload.attendance_summary; row.notes=payload.reason
        await self.audit.record(action="operations.teaching_session_status_changed", resource_type="teaching_session", resource_id=row.id, before_state={"status": before}, after_state={"status": row.status, "reason": payload.reason})
        return row

    async def list_readiness_profiles(self, module_offering_id: UUID | None = None) -> list[ModuleReadinessProfile]:
        if module_offering_id:
            await self._offering(module_offering_id, "module_readiness.read")
        else:
            await self.authorization.require_permission(tenant_id=self.context.tenant_id, user_id=self.context.user_id, permission_code="module_readiness.read")
        q = select(ModuleReadinessProfile).where(ModuleReadinessProfile.tenant_id == self.context.tenant_id)
        if module_offering_id:
            q = q.where(ModuleReadinessProfile.module_offering_id == module_offering_id)
        if self.context.role_code == "lecturer":
            q = q.where(or_(ModuleReadinessProfile.owner_user_id == self.context.user_id, ModuleReadinessProfile.module_offering_id.in_(select(LecturerAssignment.module_offering_id).where(LecturerAssignment.tenant_id == self.context.tenant_id, LecturerAssignment.user_id == self.context.user_id, LecturerAssignment.status == "active"))))
        return list(await self.session.scalars(q.order_by(ModuleReadinessProfile.updated_at.desc()).limit(300)))

    async def list_readiness_items(self, profile_id: UUID) -> list[ModuleReadinessItem]:
        await self._readiness_profile(profile_id, "module_readiness.read")
        return list(await self.session.scalars(select(ModuleReadinessItem).where(ModuleReadinessItem.tenant_id == self.context.tenant_id, ModuleReadinessItem.readiness_profile_id == profile_id).order_by(ModuleReadinessItem.category, ModuleReadinessItem.title)))

    async def create_readiness_profile(self, payload) -> ModuleReadinessProfile:
        offering=await self._offering(payload.module_offering_id, "module_readiness.manage")
        existing=await self.session.scalar(select(ModuleReadinessProfile).where(ModuleReadinessProfile.tenant_id == self.context.tenant_id, ModuleReadinessProfile.module_offering_id == offering.id))
        if existing: raise HTTPException(status_code=409, detail="A readiness profile already exists for this offering.")
        profile=ModuleReadinessProfile(id=uuid4(), tenant_id=self.context.tenant_id, module_offering_id=offering.id, organisational_unit_id=offering.org_unit_id, owner_user_id=payload.owner_user_id, due_at=payload.due_at)
        self.session.add(profile); await self.session.flush()
        for item in payload.requirements:
            values={"requirement_code": item.get("requirement_code"), "category": item.get("category", "general"), "title": item.get("title"), "description": item.get("description"), "required": item.get("required", True), "blocking": item.get("blocking", False), "weight": Decimal(str(item.get("weight", 1))), "due_at": item.get("due_at")}
            if not values["requirement_code"] or not values["title"]: raise HTTPException(status_code=422, detail="Each readiness requirement needs requirement_code and title.")
            self.session.add(ModuleReadinessItem(id=uuid4(), tenant_id=self.context.tenant_id, readiness_profile_id=profile.id, **values))
        await self.session.flush(); await self.evaluate_readiness(profile.id)
        await self.audit.record(action="operations.readiness_profile_created", resource_type="module_readiness_profile", resource_id=profile.id, after_state={"module_offering_id": str(offering.id)})
        return profile

    async def add_readiness_item(self, profile_id: UUID, payload) -> ModuleReadinessItem:
        profile=await self._readiness_profile(profile_id, "module_readiness.manage")
        item=ModuleReadinessItem(id=uuid4(), tenant_id=self.context.tenant_id, readiness_profile_id=profile.id, **payload.model_dump())
        self.session.add(item); await self.session.flush(); await self.evaluate_readiness(profile.id); return item

    async def update_readiness_item(self, item_id: UUID, payload) -> ModuleReadinessItem:
        item=await self.session.scalar(select(ModuleReadinessItem).where(ModuleReadinessItem.tenant_id == self.context.tenant_id, ModuleReadinessItem.id == item_id).with_for_update())
        if not item: raise HTTPException(status_code=404, detail="Readiness item was not found.")
        profile=await self._readiness_profile(item.readiness_profile_id, "module_readiness.manage")
        item.status=payload.status; item.evidence_document_version_ids=[str(x) for x in payload.evidence_document_version_ids]; item.waiver_reason=payload.waiver_reason; item.notes=payload.notes
        if payload.status in ReadinessCalculator.COMPLETED: item.completed_by_user_id=self.context.user_id; item.completed_at=datetime.now(timezone.utc)
        else: item.completed_by_user_id=None; item.completed_at=None
        await self.session.flush(); await self.evaluate_readiness(profile.id)
        await self.audit.record(action="operations.readiness_item_updated", resource_type="module_readiness_item", resource_id=item.id, after_state={"status": item.status})
        return item

    async def _readiness_profile(self, profile_id: UUID, permission: str) -> ModuleReadinessProfile:
        profile=await self.session.scalar(select(ModuleReadinessProfile).where(ModuleReadinessProfile.tenant_id == self.context.tenant_id, ModuleReadinessProfile.id == profile_id))
        if not profile: raise HTTPException(status_code=404, detail="Readiness profile was not found.")
        await self.authorization.require_permission(tenant_id=self.context.tenant_id, user_id=self.context.user_id, permission_code=permission, scope_type="organisational_unit", scope_id=profile.organisational_unit_id)
        return profile

    async def evaluate_readiness(self, profile_id: UUID) -> ModuleReadinessProfile:
        profile=await self.session.scalar(select(ModuleReadinessProfile).where(ModuleReadinessProfile.tenant_id == self.context.tenant_id, ModuleReadinessProfile.id == profile_id).with_for_update())
        if not profile: raise HTTPException(status_code=404, detail="Readiness profile was not found.")
        items=list(await self.session.scalars(select(ModuleReadinessItem).where(ModuleReadinessItem.tenant_id == self.context.tenant_id, ModuleReadinessItem.readiness_profile_id == profile.id)))
        score, readiness, blocking=ReadinessCalculator.calculate([{"status": x.status, "weight": x.weight, "blocking": x.blocking} for x in items])
        profile.readiness_score=score; profile.status=readiness; profile.blocking_item_count=blocking; profile.evaluated_at=datetime.now(timezone.utc); profile.evaluated_by_user_id=self.context.user_id
        await self.session.flush(); return profile

    async def create_workload_activity(self, payload) -> WorkloadActivity:
        if payload.module_offering_id: await self._offering(payload.module_offering_id, "workload.manage")
        else: await self.authorization.require_permission(tenant_id=self.context.tenant_id, user_id=self.context.user_id, permission_code="workload.manage")
        row=WorkloadActivity(id=uuid4(), tenant_id=self.context.tenant_id, user_id=payload.user_id, academic_period_id=payload.academic_period_id, module_offering_id=payload.module_offering_id, created_by_user_id=self.context.user_id, activity_type=payload.activity_type, description=payload.description, allocated_hours=payload.allocated_hours, weighting_factor=payload.weighting_factor, effective_from=payload.effective_from, effective_until=payload.effective_until, activity_metadata=payload.metadata)
        self.session.add(row); await self.session.flush(); await self.audit.record(action="operations.workload_activity_created", resource_type="workload_activity", resource_id=row.id, after_state={"user_id": str(row.user_id), "allocated_hours": str(row.allocated_hours)})
        return row

    async def end_workload_activity(self, activity_id: UUID, payload) -> WorkloadActivity:
        row = await self.session.scalar(select(WorkloadActivity).where(WorkloadActivity.tenant_id == self.context.tenant_id, WorkloadActivity.id == activity_id).with_for_update())
        if row is None:
            raise HTTPException(status_code=404, detail="Workload activity was not found.")
        if row.module_offering_id:
            await self._offering(row.module_offering_id, "workload.manage")
        else:
            await self.authorization.require_permission(tenant_id=self.context.tenant_id, user_id=self.context.user_id, permission_code="workload.manage")
        if row.status != "active":
            raise HTTPException(status_code=409, detail="Only an active workload activity may be ended.")
        row.status = "ended"
        row.effective_until = payload.effective_until or date.today()
        await self.audit.record(action="operations.workload_activity_ended", resource_type="workload_activity", resource_id=row.id, after_state={"effective_until": row.effective_until.isoformat(), "reason": payload.reason})
        return row

    async def workload_summary(self, user_id: UUID, academic_period_id: UUID) -> WorkloadSummary:
        own=self.context.user_id == user_id
        await self.authorization.require_permission(tenant_id=self.context.tenant_id, user_id=self.context.user_id, permission_code="workload.read_own" if own else "academic.workload.review")
        rows=list(await self.session.scalars(select(WorkloadActivity).where(WorkloadActivity.tenant_id == self.context.tenant_id, WorkloadActivity.user_id == user_id, WorkloadActivity.academic_period_id == academic_period_id, WorkloadActivity.status == "active").order_by(WorkloadActivity.created_at)))
        limit=await self.session.scalar(select(TeachingWorkload.workload_limit_hours).where(TeachingWorkload.tenant_id == self.context.tenant_id, TeachingWorkload.user_id == user_id, TeachingWorkload.academic_period_id == academic_period_id))
        raw, weighted, utilisation, overloaded=WorkloadCalculator.summarise([(Decimal(x.allocated_hours), Decimal(x.weighting_factor)) for x in rows], Decimal(limit) if limit is not None else None)
        return WorkloadSummary(user_id=user_id, academic_period_id=academic_period_id, activity_count=len(rows), raw_allocated_hours=raw, weighted_hours=weighted, workload_limit_hours=limit, utilisation_percentage=utilisation, overloaded=overloaded, activities=rows)

    async def create_handover(self, payload) -> tuple[HandoverPackage, HandoverVersion]:
        offering=await self._offering(payload.module_offering_id, "handover.manage")
        if self.context.role_code == "lecturer" and payload.outgoing_user_id != self.context.user_id:
            raise HTTPException(status_code=403, detail="A lecturer may prepare only their own outgoing handover package.")
        package=HandoverPackage(id=uuid4(), tenant_id=self.context.tenant_id, module_offering_id=offering.id, outgoing_user_id=payload.outgoing_user_id, incoming_user_id=payload.incoming_user_id, initiated_by_user_id=self.context.user_id, title=payload.title, due_at=payload.due_at)
        self.session.add(package); await self.session.flush()
        version=await self._new_handover_version(package, change_reason="Initial handover package", summary=payload.summary, checklist=payload.checklist, document_version_ids=[str(x) for x in payload.document_version_ids], open_actions=payload.open_actions, risks_and_dependencies=payload.risks_and_dependencies)
        await self.audit.record(action="operations.handover_created", resource_type="handover_package", resource_id=package.id, after_state={"module_offering_id": str(offering.id), "outgoing_user_id": str(package.outgoing_user_id), "incoming_user_id": str(package.incoming_user_id) if package.incoming_user_id else None})
        return package, version

    async def _new_handover_version(self, package: HandoverPackage, **values) -> HandoverVersion:
        current=await self.session.scalar(select(HandoverVersion).where(HandoverVersion.tenant_id == self.context.tenant_id, HandoverVersion.handover_package_id == package.id, HandoverVersion.is_current.is_(True)).with_for_update())
        if current: current.is_current=False
        number=(current.version_number+1) if current else 1
        payload={k: values[k] for k in ("summary","checklist","document_version_ids","open_actions","risks_and_dependencies")}
        row=HandoverVersion(id=uuid4(), tenant_id=self.context.tenant_id, handover_package_id=package.id, version_number=number, previous_version_id=current.id if current else None, created_by_user_id=self.context.user_id, change_reason=values["change_reason"], checksum_sha256=canonical_checksum(payload), is_current=True, **payload)
        self.session.add(row); await self.session.flush(); package.current_version_id=row.id; return row

    async def create_handover_version(self, package_id: UUID, payload) -> HandoverVersion:
        package=await self._handover(package_id, "handover.manage", lock=True)
        values=payload.model_dump(); values["document_version_ids"]=[str(x) for x in payload.document_version_ids]
        row=await self._new_handover_version(package, **values); await self.audit.record(action="operations.handover_version_created", resource_type="handover_package", resource_id=package.id, after_state={"version": row.version_number}); return row

    async def _handover(self, package_id: UUID, permission: str, lock: bool=False) -> HandoverPackage:
        q=select(HandoverPackage).where(HandoverPackage.tenant_id == self.context.tenant_id, HandoverPackage.id == package_id)
        if lock: q=q.with_for_update()
        package=await self.session.scalar(q)
        if not package: raise HTTPException(status_code=404, detail="Handover package was not found.")
        await self._offering(package.module_offering_id, permission)
        return package

    async def list_handover_versions(self, package_id: UUID) -> list[HandoverVersion]:
        package = await self._handover(package_id, "handover.read")
        return list(await self.session.scalars(select(HandoverVersion).where(HandoverVersion.tenant_id == self.context.tenant_id, HandoverVersion.handover_package_id == package.id).order_by(HandoverVersion.version_number.desc())))

    async def transition_handover(self, package_id: UUID, payload) -> tuple[HandoverPackage, HandoverAction]:
        package=await self._handover(package_id, "handover.manage" if payload.action not in {"accept"} else "handover.accept", lock=True)
        if payload.action == "accept" and package.incoming_user_id not in {None, self.context.user_id} and self.context.role_code not in {"head_of_department", "module_coordinator"}:
            raise HTTPException(status_code=403, detail="Only the assigned incoming lecturer or authorised academic manager may accept this handover.")
        before=package.status
        try: after=HandoverStateMachine.transition(before, payload.action)
        except ValueError as exc: raise HTTPException(status_code=409, detail=str(exc)) from exc
        package.status=after; now=datetime.now(timezone.utc)
        if after == HandoverStatus.SUBMITTED.value: package.submitted_at=now
        elif after == HandoverStatus.ACCEPTED.value: package.accepted_at=now
        elif after == HandoverStatus.COMPLETED.value: package.completed_at=now
        action=HandoverAction(id=uuid4(), tenant_id=self.context.tenant_id, handover_package_id=package.id, acted_by_user_id=self.context.user_id, actor_role_code=self.context.role_code, action=payload.action, from_status=before, to_status=after, reason=payload.reason)
        self.session.add(action); await self.session.flush(); await self.audit.record(action="operations.handover_transitioned", resource_type="handover_package", resource_id=package.id, before_state={"status": before}, after_state={"status": after, "reason": payload.reason})
        return package, action

    async def list_handovers(self, module_offering_id: UUID | None = None) -> list[HandoverPackage]:
        await self.authorization.require_permission(tenant_id=self.context.tenant_id, user_id=self.context.user_id, permission_code="handover.read")
        q=select(HandoverPackage).where(HandoverPackage.tenant_id == self.context.tenant_id)
        if module_offering_id: q=q.where(HandoverPackage.module_offering_id == module_offering_id)
        if self.context.role_code == "lecturer": q=q.where(or_(HandoverPackage.outgoing_user_id == self.context.user_id, HandoverPackage.incoming_user_id == self.context.user_id))
        return list(await self.session.scalars(q.order_by(HandoverPackage.updated_at.desc()).limit(300)))

    async def dashboard(self, organisational_unit_id: UUID) -> DepartmentOperationsDashboard:
        await self.authorization.require_permission(tenant_id=self.context.tenant_id, user_id=self.context.user_id, permission_code="department.operations.read", scope_type="organisational_unit", scope_id=organisational_unit_id)
        now=datetime.now(timezone.utc)
        offering_ids=list(await self.session.scalars(select(ModuleOffering.id).where(ModuleOffering.tenant_id == self.context.tenant_id, ModuleOffering.org_unit_id == organisational_unit_id, or_(ModuleOffering.ends_on.is_(None), ModuleOffering.ends_on >= now.date()))))
        if not offering_ids:
            return DepartmentOperationsDashboard(organisational_unit_id=organisational_unit_id, active_module_offerings=0, modules_without_active_teaching_plan=0, planned_sessions=0, delivered_sessions=0, missed_or_cancelled_sessions=0, readiness_ready=0, readiness_at_risk_or_blocked=0, overdue_readiness_profiles=0, overloaded_lecturers=0, open_handovers=0, overdue_handovers=0, upcoming_calendar_events=0, unresolved_operational_alerts=0, attention_items=[])
        active_plans=await self.session.scalar(select(func.count(func.distinct(TeachingPlan.module_offering_id))).where(TeachingPlan.tenant_id == self.context.tenant_id, TeachingPlan.module_offering_id.in_(offering_ids), TeachingPlan.status.in_(["draft","active","paused"]))) or 0
        sess_counts=dict((await self.session.execute(select(TeachingSession.status, func.count(TeachingSession.id)).where(TeachingSession.tenant_id == self.context.tenant_id, TeachingSession.module_offering_id.in_(offering_ids)).group_by(TeachingSession.status))).all())
        ready=await self.session.scalar(select(func.count(ModuleReadinessProfile.id)).where(ModuleReadinessProfile.tenant_id == self.context.tenant_id, ModuleReadinessProfile.module_offering_id.in_(offering_ids), ModuleReadinessProfile.status == "ready")) or 0
        risk=await self.session.scalar(select(func.count(ModuleReadinessProfile.id)).where(ModuleReadinessProfile.tenant_id == self.context.tenant_id, ModuleReadinessProfile.module_offering_id.in_(offering_ids), ModuleReadinessProfile.status.in_(["at_risk","blocked"]))) or 0
        overdue_readiness=await self.session.scalar(select(func.count(ModuleReadinessProfile.id)).where(ModuleReadinessProfile.tenant_id == self.context.tenant_id, ModuleReadinessProfile.module_offering_id.in_(offering_ids), ModuleReadinessProfile.due_at < now, ModuleReadinessProfile.status != "ready")) or 0
        handovers=list(await self.session.scalars(select(HandoverPackage).where(HandoverPackage.tenant_id == self.context.tenant_id, HandoverPackage.module_offering_id.in_(offering_ids), HandoverPackage.status.not_in(["completed","archived"]))))
        upcoming=await self.session.scalar(select(func.count(AcademicCalendarEvent.id)).where(AcademicCalendarEvent.tenant_id == self.context.tenant_id, or_(AcademicCalendarEvent.organisational_unit_id == organisational_unit_id, AcademicCalendarEvent.module_offering_id.in_(offering_ids)), AcademicCalendarEvent.starts_at >= now, AcademicCalendarEvent.status == "scheduled")) or 0
        alerts=await self.session.scalar(select(func.count(OperationalAlert.id)).where(OperationalAlert.tenant_id == self.context.tenant_id, OperationalAlert.organisational_unit_id == organisational_unit_id, OperationalAlert.resolved_at.is_(None))) or 0
        # Workload overload uses persisted aggregate limits and active activities.
        workload_rows=(await self.session.execute(select(WorkloadActivity.user_id, func.sum(WorkloadActivity.allocated_hours * WorkloadActivity.weighting_factor)).where(WorkloadActivity.tenant_id == self.context.tenant_id, WorkloadActivity.module_offering_id.in_(offering_ids), WorkloadActivity.status == "active").group_by(WorkloadActivity.user_id))).all()
        overloaded=0
        for user_id, weighted in workload_rows:
            limit=await self.session.scalar(select(TeachingWorkload.workload_limit_hours).where(TeachingWorkload.tenant_id == self.context.tenant_id, TeachingWorkload.user_id == user_id))
            if limit is not None and weighted is not None and Decimal(weighted) > Decimal(limit): overloaded += 1
        attention=[]
        if len(offering_ids)-int(active_plans)>0: attention.append({"type":"missing_teaching_plan","severity":"high","count":len(offering_ids)-int(active_plans),"message":"Active module offerings do not yet have an active teaching plan."})
        if risk: attention.append({"type":"module_readiness","severity":"high","count":int(risk),"message":"Module offerings are at risk or blocked."})
        overdue_handovers=sum(1 for x in handovers if x.due_at and x.due_at < now)
        if overdue_handovers: attention.append({"type":"handover_overdue","severity":"medium","count":overdue_handovers,"message":"Lecturer handover packages are overdue."})
        if overloaded: attention.append({"type":"workload_overload","severity":"high","count":overloaded,"message":"Lecturer workload exceeds configured limits."})
        return DepartmentOperationsDashboard(organisational_unit_id=organisational_unit_id, active_module_offerings=len(offering_ids), modules_without_active_teaching_plan=max(0,len(offering_ids)-int(active_plans)), planned_sessions=int(sess_counts.get("planned",0)+sess_counts.get("rescheduled",0)), delivered_sessions=int(sess_counts.get("delivered",0)), missed_or_cancelled_sessions=int(sess_counts.get("missed",0)+sess_counts.get("cancelled",0)), readiness_ready=int(ready), readiness_at_risk_or_blocked=int(risk), overdue_readiness_profiles=int(overdue_readiness), overloaded_lecturers=overloaded, open_handovers=len(handovers), overdue_handovers=overdue_handovers, upcoming_calendar_events=int(upcoming), unresolved_operational_alerts=int(alerts), attention_items=attention)
