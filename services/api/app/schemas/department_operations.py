from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from .common import ORMModel


class CalendarEventCreate(BaseModel):
    academic_period_id: UUID
    organisational_unit_id: UUID | None = None
    module_offering_id: UUID | None = None
    event_type: str = Field(min_length=2, max_length=80)
    title: str = Field(min_length=3, max_length=300)
    description: str | None = Field(default=None, max_length=5000)
    starts_at: datetime
    ends_at: datetime
    all_day: bool = False
    visibility: str = Field(default="department", pattern="^(private|module|programme|department|institution)$")
    recurrence_rule: str | None = Field(default=None, max_length=500)
    metadata: dict = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_dates(self):
        if self.ends_at <= self.starts_at:
            raise ValueError("ends_at must be later than starts_at")
        return self


class CalendarEventStatusUpdate(BaseModel):
    action: str = Field(pattern="^(complete|cancel)$")
    reason: str = Field(min_length=3, max_length=2000)


class CalendarEventRead(ORMModel):
    id: UUID
    academic_period_id: UUID
    organisational_unit_id: UUID | None
    module_offering_id: UUID | None
    event_type: str
    title: str
    description: str | None
    starts_at: datetime
    ends_at: datetime
    all_day: bool
    status: str
    visibility: str
    recurrence_rule: str | None
    created_by_user_id: UUID
    created_at: datetime


class TeachingPlanCreate(BaseModel):
    module_offering_id: UUID
    title: str = Field(min_length=3, max_length=300)
    planned_contact_hours: Decimal | None = Field(default=None, ge=0, le=10000)
    starts_on: date | None = None
    ends_on: date | None = None
    summary: str | None = Field(default=None, max_length=10000)
    weekly_schedule: list[dict] = Field(default_factory=list)
    learning_outcome_mapping: list[dict] = Field(default_factory=list)
    assessment_milestones: list[dict] = Field(default_factory=list)
    resource_requirements: list[dict] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_dates(self):
        if self.starts_on and self.ends_on and self.ends_on < self.starts_on:
            raise ValueError("ends_on cannot be before starts_on")
        return self


class TeachingPlanStatusUpdate(BaseModel):
    action: str = Field(pattern="^(activate|pause|complete|archive)$")
    reason: str = Field(min_length=3, max_length=2000)


class TeachingPlanVersionCreate(BaseModel):
    change_reason: str = Field(min_length=3, max_length=1000)
    summary: str | None = Field(default=None, max_length=10000)
    weekly_schedule: list[dict] = Field(default_factory=list)
    learning_outcome_mapping: list[dict] = Field(default_factory=list)
    assessment_milestones: list[dict] = Field(default_factory=list)
    resource_requirements: list[dict] = Field(default_factory=list)


class TeachingPlanVersionRead(ORMModel):
    id: UUID
    teaching_plan_id: UUID
    version_number: int
    previous_version_id: UUID | None
    created_by_user_id: UUID
    change_reason: str
    summary: str | None
    weekly_schedule: list
    learning_outcome_mapping: list
    assessment_milestones: list
    resource_requirements: list
    checksum_sha256: str
    is_current: bool
    created_at: datetime


class TeachingPlanRead(ORMModel):
    id: UUID
    module_offering_id: UUID
    academic_period_id: UUID
    owner_user_id: UUID
    title: str
    status: str
    planned_contact_hours: Decimal | None
    current_version_id: UUID | None
    starts_on: date | None
    ends_on: date | None
    created_at: datetime


class TeachingSessionCreate(BaseModel):
    topic: str = Field(min_length=2, max_length=500)
    session_type: str = Field(min_length=2, max_length=80)
    planned_start: datetime
    planned_end: datetime
    learning_outcome_ids: list[UUID] = Field(default_factory=list)
    notes: str | None = Field(default=None, max_length=5000)

    @model_validator(mode="after")
    def validate_dates(self):
        if self.planned_end <= self.planned_start:
            raise ValueError("planned_end must be later than planned_start")
        return self


class TeachingSessionStatusUpdate(BaseModel):
    action: str = Field(pattern="^(deliver|reschedule|cancel|mark_missed)$")
    reason: str = Field(min_length=3, max_length=2000)
    actual_start: datetime | None = None
    actual_end: datetime | None = None
    evidence_document_version_ids: list[UUID] = Field(default_factory=list)
    attendance_summary: dict = Field(default_factory=dict)


class TeachingSessionRead(ORMModel):
    id: UUID
    teaching_plan_id: UUID
    module_offering_id: UUID
    delivered_by_user_id: UUID | None
    topic: str
    session_type: str
    planned_start: datetime
    planned_end: datetime
    actual_start: datetime | None
    actual_end: datetime | None
    status: str
    learning_outcome_ids: list
    evidence_document_version_ids: list
    attendance_summary: dict
    notes: str | None
    created_at: datetime


class ReadinessProfileCreate(BaseModel):
    module_offering_id: UUID
    owner_user_id: UUID | None = None
    due_at: datetime | None = None
    requirements: list[dict] = Field(default_factory=list)


class ReadinessItemCreate(BaseModel):
    requirement_code: str = Field(min_length=2, max_length=100)
    category: str = Field(min_length=2, max_length=100)
    title: str = Field(min_length=3, max_length=300)
    description: str | None = Field(default=None, max_length=5000)
    required: bool = True
    blocking: bool = False
    weight: Decimal = Field(default=Decimal("1"), gt=0, le=100)
    due_at: datetime | None = None


class ReadinessItemUpdate(BaseModel):
    status: str = Field(pattern="^(missing|in_progress|complete|waived|not_applicable)$")
    evidence_document_version_ids: list[UUID] = Field(default_factory=list)
    waiver_reason: str | None = Field(default=None, max_length=3000)
    notes: str | None = Field(default=None, max_length=5000)

    @model_validator(mode="after")
    def validate_waiver(self):
        if self.status == "waived" and not self.waiver_reason:
            raise ValueError("waiver_reason is required when status is waived")
        return self


class ReadinessItemRead(ORMModel):
    id: UUID
    readiness_profile_id: UUID
    requirement_code: str
    category: str
    title: str
    required: bool
    blocking: bool
    weight: Decimal
    status: str
    due_at: datetime | None
    evidence_document_version_ids: list
    waiver_reason: str | None
    completed_at: datetime | None


class ReadinessProfileRead(ORMModel):
    id: UUID
    module_offering_id: UUID
    organisational_unit_id: UUID
    owner_user_id: UUID | None
    status: str
    readiness_score: Decimal
    due_at: datetime | None
    evaluated_at: datetime | None
    blocking_item_count: int
    created_at: datetime


class WorkloadActivityCreate(BaseModel):
    user_id: UUID
    academic_period_id: UUID
    module_offering_id: UUID | None = None
    activity_type: str = Field(min_length=2, max_length=100)
    description: str = Field(min_length=3, max_length=500)
    allocated_hours: Decimal = Field(gt=0, le=10000)
    weighting_factor: Decimal = Field(default=Decimal("1"), gt=0, le=20)
    effective_from: date
    effective_until: date | None = None
    metadata: dict = Field(default_factory=dict)


class WorkloadActivityEnd(BaseModel):
    reason: str = Field(min_length=3, max_length=2000)
    effective_until: date | None = None


class WorkloadActivityRead(ORMModel):
    id: UUID
    user_id: UUID
    academic_period_id: UUID
    module_offering_id: UUID | None
    activity_type: str
    description: str
    allocated_hours: Decimal
    weighting_factor: Decimal
    effective_from: date
    effective_until: date | None
    status: str
    created_at: datetime


class WorkloadSummary(BaseModel):
    user_id: UUID
    academic_period_id: UUID
    activity_count: int
    raw_allocated_hours: Decimal
    weighted_hours: Decimal
    workload_limit_hours: Decimal | None
    utilisation_percentage: Decimal | None
    overloaded: bool
    activities: list[WorkloadActivityRead]


class HandoverCreate(BaseModel):
    module_offering_id: UUID
    outgoing_user_id: UUID
    incoming_user_id: UUID | None = None
    title: str = Field(min_length=3, max_length=300)
    due_at: datetime | None = None
    summary: str | None = Field(default=None, max_length=10000)
    checklist: list[dict] = Field(default_factory=list)
    document_version_ids: list[UUID] = Field(default_factory=list)
    open_actions: list[dict] = Field(default_factory=list)
    risks_and_dependencies: list[dict] = Field(default_factory=list)


class HandoverVersionCreate(BaseModel):
    change_reason: str = Field(min_length=3, max_length=1000)
    summary: str | None = Field(default=None, max_length=10000)
    checklist: list[dict] = Field(default_factory=list)
    document_version_ids: list[UUID] = Field(default_factory=list)
    open_actions: list[dict] = Field(default_factory=list)
    risks_and_dependencies: list[dict] = Field(default_factory=list)


class HandoverTransition(BaseModel):
    action: str = Field(pattern="^(submit|request_changes|accept|complete|archive)$")
    reason: str = Field(min_length=3, max_length=3000)


class HandoverVersionRead(ORMModel):
    id: UUID
    handover_package_id: UUID
    version_number: int
    previous_version_id: UUID | None
    created_by_user_id: UUID
    change_reason: str
    summary: str | None
    checklist: list
    document_version_ids: list
    open_actions: list
    risks_and_dependencies: list
    checksum_sha256: str
    is_current: bool
    created_at: datetime


class HandoverRead(ORMModel):
    id: UUID
    module_offering_id: UUID
    outgoing_user_id: UUID
    incoming_user_id: UUID | None
    initiated_by_user_id: UUID
    status: str
    title: str
    due_at: datetime | None
    current_version_id: UUID | None
    submitted_at: datetime | None
    accepted_at: datetime | None
    completed_at: datetime | None
    created_at: datetime


class DepartmentOperationsDashboard(BaseModel):
    organisational_unit_id: UUID
    active_module_offerings: int
    modules_without_active_teaching_plan: int
    planned_sessions: int
    delivered_sessions: int
    missed_or_cancelled_sessions: int
    readiness_ready: int
    readiness_at_risk_or_blocked: int
    overdue_readiness_profiles: int
    overloaded_lecturers: int
    open_handovers: int
    overdue_handovers: int
    upcoming_calendar_events: int
    unresolved_operational_alerts: int
    attention_items: list[dict]
