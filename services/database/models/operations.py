from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Index, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, TenantOwnedMixin, TimestampMixin, UUIDPrimaryKeyMixin
from .enums import (
    AcademicCalendarEventStatus,
    HandoverStatus,
    ModuleReadinessStatus,
    ReadinessItemStatus,
    TeachingPlanStatus,
    TeachingSessionStatus,
    WorkloadActivityStatus,
)


class AcademicCalendarEvent(Base, UUIDPrimaryKeyMixin, TenantOwnedMixin, TimestampMixin):
    __tablename__ = "academic_calendar_events"
    __table_args__ = (
        Index("ix_calendar_event_scope_time", "tenant_id", "organisational_unit_id", "starts_at"),
        Index("ix_calendar_event_offering", "tenant_id", "module_offering_id", "starts_at"),
        {"schema": "academic"},
    )

    academic_period_id: Mapped[UUID] = mapped_column(ForeignKey("tenant.academic_periods.id"), nullable=False)
    organisational_unit_id: Mapped[UUID | None] = mapped_column(ForeignKey("tenant.organisational_units.id"))
    module_offering_id: Mapped[UUID | None] = mapped_column(ForeignKey("academic.module_offerings.id"))
    created_by_user_id: Mapped[UUID] = mapped_column(ForeignKey("iam.users.id"), nullable=False)
    event_type: Mapped[str] = mapped_column(String(80), nullable=False)
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    all_day: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    status: Mapped[str] = mapped_column(String(30), default=AcademicCalendarEventStatus.SCHEDULED.value, nullable=False)
    visibility: Mapped[str] = mapped_column(String(30), default="department", nullable=False)
    recurrence_rule: Mapped[str | None] = mapped_column(String(500))
    event_metadata: Mapped[dict] = mapped_column("metadata", JSONB, default=dict, nullable=False)


class TeachingPlan(Base, UUIDPrimaryKeyMixin, TenantOwnedMixin, TimestampMixin):
    __tablename__ = "teaching_plans"
    __table_args__ = (
        UniqueConstraint("tenant_id", "module_offering_id", "owner_user_id", "title"),
        Index("ix_teaching_plan_offering_status", "tenant_id", "module_offering_id", "status"),
        {"schema": "academic"},
    )

    module_offering_id: Mapped[UUID] = mapped_column(ForeignKey("academic.module_offerings.id"), nullable=False)
    academic_period_id: Mapped[UUID] = mapped_column(ForeignKey("tenant.academic_periods.id"), nullable=False)
    owner_user_id: Mapped[UUID] = mapped_column(ForeignKey("iam.users.id"), nullable=False)
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    status: Mapped[str] = mapped_column(String(30), default=TeachingPlanStatus.DRAFT.value, nullable=False)
    planned_contact_hours: Mapped[Decimal | None] = mapped_column(Numeric(8, 2))
    current_version_id: Mapped[UUID | None] = mapped_column(nullable=True)
    starts_on: Mapped[date | None] = mapped_column(Date)
    ends_on: Mapped[date | None] = mapped_column(Date)
    plan_metadata: Mapped[dict] = mapped_column("metadata", JSONB, default=dict, nullable=False)


class TeachingPlanVersion(Base, UUIDPrimaryKeyMixin, TenantOwnedMixin, TimestampMixin):
    __tablename__ = "teaching_plan_versions"
    __table_args__ = (
        UniqueConstraint("tenant_id", "teaching_plan_id", "version_number"),
        Index("ix_teaching_plan_version_current", "tenant_id", "teaching_plan_id", "is_current"),
        {"schema": "academic"},
    )

    teaching_plan_id: Mapped[UUID] = mapped_column(ForeignKey("academic.teaching_plans.id", ondelete="CASCADE"), nullable=False)
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    previous_version_id: Mapped[UUID | None] = mapped_column(ForeignKey("academic.teaching_plan_versions.id"))
    created_by_user_id: Mapped[UUID] = mapped_column(ForeignKey("iam.users.id"), nullable=False)
    change_reason: Mapped[str] = mapped_column(String(1000), nullable=False)
    summary: Mapped[str | None] = mapped_column(Text)
    weekly_schedule: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    learning_outcome_mapping: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    assessment_milestones: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    resource_requirements: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    checksum_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    is_current: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class TeachingSession(Base, UUIDPrimaryKeyMixin, TenantOwnedMixin, TimestampMixin):
    __tablename__ = "teaching_sessions"
    __table_args__ = (
        Index("ix_teaching_session_plan_time", "tenant_id", "teaching_plan_id", "planned_start"),
        Index("ix_teaching_session_offering_status", "tenant_id", "module_offering_id", "status"),
        {"schema": "academic"},
    )

    teaching_plan_id: Mapped[UUID] = mapped_column(ForeignKey("academic.teaching_plans.id", ondelete="CASCADE"), nullable=False)
    module_offering_id: Mapped[UUID] = mapped_column(ForeignKey("academic.module_offerings.id"), nullable=False)
    delivered_by_user_id: Mapped[UUID | None] = mapped_column(ForeignKey("iam.users.id"))
    topic: Mapped[str] = mapped_column(String(500), nullable=False)
    session_type: Mapped[str] = mapped_column(String(80), nullable=False)
    planned_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    planned_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    actual_start: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    actual_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(30), default=TeachingSessionStatus.PLANNED.value, nullable=False)
    learning_outcome_ids: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    evidence_document_version_ids: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    attendance_summary: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text)


class ModuleReadinessProfile(Base, UUIDPrimaryKeyMixin, TenantOwnedMixin, TimestampMixin):
    __tablename__ = "module_readiness_profiles"
    __table_args__ = (
        UniqueConstraint("tenant_id", "module_offering_id"),
        Index("ix_readiness_scope_status", "tenant_id", "organisational_unit_id", "status"),
        {"schema": "academic"},
    )

    module_offering_id: Mapped[UUID] = mapped_column(ForeignKey("academic.module_offerings.id"), nullable=False)
    organisational_unit_id: Mapped[UUID] = mapped_column(ForeignKey("tenant.organisational_units.id"), nullable=False)
    owner_user_id: Mapped[UUID | None] = mapped_column(ForeignKey("iam.users.id"))
    status: Mapped[str] = mapped_column(String(30), default=ModuleReadinessStatus.NOT_STARTED.value, nullable=False)
    readiness_score: Mapped[Decimal] = mapped_column(Numeric(5, 2), default=0, nullable=False)
    due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    evaluated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    evaluated_by_user_id: Mapped[UUID | None] = mapped_column(ForeignKey("iam.users.id"))
    blocking_item_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    readiness_metadata: Mapped[dict] = mapped_column("metadata", JSONB, default=dict, nullable=False)


class ModuleReadinessItem(Base, UUIDPrimaryKeyMixin, TenantOwnedMixin, TimestampMixin):
    __tablename__ = "module_readiness_items"
    __table_args__ = (
        UniqueConstraint("tenant_id", "readiness_profile_id", "requirement_code"),
        Index("ix_readiness_item_profile_status", "tenant_id", "readiness_profile_id", "status"),
        {"schema": "academic"},
    )

    readiness_profile_id: Mapped[UUID] = mapped_column(ForeignKey("academic.module_readiness_profiles.id", ondelete="CASCADE"), nullable=False)
    requirement_code: Mapped[str] = mapped_column(String(100), nullable=False)
    category: Mapped[str] = mapped_column(String(100), nullable=False)
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    required: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    blocking: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    weight: Mapped[Decimal] = mapped_column(Numeric(6, 2), default=1, nullable=False)
    status: Mapped[str] = mapped_column(String(30), default=ReadinessItemStatus.MISSING.value, nullable=False)
    due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_by_user_id: Mapped[UUID | None] = mapped_column(ForeignKey("iam.users.id"))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    evidence_document_version_ids: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    waiver_reason: Mapped[str | None] = mapped_column(Text)
    notes: Mapped[str | None] = mapped_column(Text)


class WorkloadActivity(Base, UUIDPrimaryKeyMixin, TenantOwnedMixin, TimestampMixin):
    __tablename__ = "workload_activities"
    __table_args__ = (
        Index("ix_workload_activity_user_period", "tenant_id", "user_id", "academic_period_id"),
        Index("ix_workload_activity_offering", "tenant_id", "module_offering_id", "status"),
        {"schema": "academic"},
    )

    user_id: Mapped[UUID] = mapped_column(ForeignKey("iam.users.id"), nullable=False)
    academic_period_id: Mapped[UUID] = mapped_column(ForeignKey("tenant.academic_periods.id"), nullable=False)
    module_offering_id: Mapped[UUID | None] = mapped_column(ForeignKey("academic.module_offerings.id"))
    created_by_user_id: Mapped[UUID] = mapped_column(ForeignKey("iam.users.id"), nullable=False)
    activity_type: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str] = mapped_column(String(500), nullable=False)
    allocated_hours: Mapped[Decimal] = mapped_column(Numeric(8, 2), nullable=False)
    weighting_factor: Mapped[Decimal] = mapped_column(Numeric(6, 3), default=1, nullable=False)
    effective_from: Mapped[date] = mapped_column(Date, nullable=False)
    effective_until: Mapped[date | None] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(30), default=WorkloadActivityStatus.ACTIVE.value, nullable=False)
    activity_metadata: Mapped[dict] = mapped_column("metadata", JSONB, default=dict, nullable=False)


class HandoverPackage(Base, UUIDPrimaryKeyMixin, TenantOwnedMixin, TimestampMixin):
    __tablename__ = "handover_packages"
    __table_args__ = (
        Index("ix_handover_offering_status", "tenant_id", "module_offering_id", "status"),
        Index("ix_handover_users", "tenant_id", "outgoing_user_id", "incoming_user_id"),
        {"schema": "academic"},
    )

    module_offering_id: Mapped[UUID] = mapped_column(ForeignKey("academic.module_offerings.id"), nullable=False)
    outgoing_user_id: Mapped[UUID] = mapped_column(ForeignKey("iam.users.id"), nullable=False)
    incoming_user_id: Mapped[UUID | None] = mapped_column(ForeignKey("iam.users.id"))
    initiated_by_user_id: Mapped[UUID] = mapped_column(ForeignKey("iam.users.id"), nullable=False)
    status: Mapped[str] = mapped_column(String(30), default=HandoverStatus.DRAFT.value, nullable=False)
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    current_version_id: Mapped[UUID | None] = mapped_column(nullable=True)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    handover_metadata: Mapped[dict] = mapped_column("metadata", JSONB, default=dict, nullable=False)


class HandoverVersion(Base, UUIDPrimaryKeyMixin, TenantOwnedMixin, TimestampMixin):
    __tablename__ = "handover_versions"
    __table_args__ = (
        UniqueConstraint("tenant_id", "handover_package_id", "version_number"),
        Index("ix_handover_version_current", "tenant_id", "handover_package_id", "is_current"),
        {"schema": "academic"},
    )

    handover_package_id: Mapped[UUID] = mapped_column(ForeignKey("academic.handover_packages.id", ondelete="CASCADE"), nullable=False)
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    previous_version_id: Mapped[UUID | None] = mapped_column(ForeignKey("academic.handover_versions.id"))
    created_by_user_id: Mapped[UUID] = mapped_column(ForeignKey("iam.users.id"), nullable=False)
    change_reason: Mapped[str] = mapped_column(String(1000), nullable=False)
    summary: Mapped[str | None] = mapped_column(Text)
    checklist: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    document_version_ids: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    open_actions: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    risks_and_dependencies: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    checksum_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    is_current: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class HandoverAction(Base, UUIDPrimaryKeyMixin, TenantOwnedMixin, TimestampMixin):
    __tablename__ = "handover_actions"
    __table_args__ = (
        Index("ix_handover_action_package", "tenant_id", "handover_package_id", "created_at"),
        {"schema": "academic"},
    )

    handover_package_id: Mapped[UUID] = mapped_column(ForeignKey("academic.handover_packages.id", ondelete="CASCADE"), nullable=False)
    acted_by_user_id: Mapped[UUID] = mapped_column(ForeignKey("iam.users.id"), nullable=False)
    actor_role_code: Mapped[str] = mapped_column(String(80), nullable=False)
    action: Mapped[str] = mapped_column(String(60), nullable=False)
    from_status: Mapped[str] = mapped_column(String(30), nullable=False)
    to_status: Mapped[str] = mapped_column(String(30), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    action_metadata: Mapped[dict] = mapped_column("metadata", JSONB, default=dict, nullable=False)


class OperationalAlert(Base, UUIDPrimaryKeyMixin, TenantOwnedMixin, TimestampMixin):
    __tablename__ = "operational_alerts"
    __table_args__ = (
        Index("ix_operational_alert_scope", "tenant_id", "organisational_unit_id", "resolved_at"),
        Index("ix_operational_alert_resource", "tenant_id", "resource_type", "resource_id"),
        {"schema": "governance"},
    )

    organisational_unit_id: Mapped[UUID | None] = mapped_column(ForeignKey("tenant.organisational_units.id"))
    resource_type: Mapped[str] = mapped_column(String(80), nullable=False)
    resource_id: Mapped[UUID | None] = mapped_column(nullable=True)
    alert_type: Mapped[str] = mapped_column(String(100), nullable=False)
    severity: Mapped[str] = mapped_column(String(30), nullable=False)
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    detected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    resolved_by_user_id: Mapped[UUID | None] = mapped_column(ForeignKey("iam.users.id"))
    resolution_note: Mapped[str | None] = mapped_column(Text)
    alert_metadata: Mapped[dict] = mapped_column("metadata", JSONB, default=dict, nullable=False)
