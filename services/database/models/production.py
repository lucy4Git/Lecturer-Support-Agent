from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, TenantOwnedMixin, TimestampMixin, UUIDPrimaryKeyMixin
from .enums import (
    AssessmentRiskLevel,
    ExportAudience,
    ExportFormat,
    ExportStatus,
    OutputWorkflowStatus,
    SafetyReviewStatus,
)


class ModuleContextSnapshot(Base, UUIDPrimaryKeyMixin, TenantOwnedMixin, TimestampMixin):
    """Immutable academic context used for one AI request.

    The snapshot prevents later changes to a module, outcome, or offering from
    rewriting the evidence behind an already generated teaching output.
    """

    __tablename__ = "module_context_snapshots"
    __table_args__ = (
        UniqueConstraint("tenant_id", "ai_request_id"),
        Index("ix_module_context_offering", "tenant_id", "module_offering_id"),
        {"schema": "academic"},
    )

    ai_request_id: Mapped[UUID] = mapped_column(ForeignKey("ai.ai_requests.id"), nullable=False)
    conversation_id: Mapped[UUID] = mapped_column(
        ForeignKey("conversation.conversations.id"), nullable=False
    )
    requested_by_user_id: Mapped[UUID] = mapped_column(ForeignKey("iam.users.id"), nullable=False)
    module_id: Mapped[UUID] = mapped_column(ForeignKey("academic.modules.id"), nullable=False)
    module_offering_id: Mapped[UUID] = mapped_column(
        ForeignKey("academic.module_offerings.id"), nullable=False
    )
    context_source: Mapped[str] = mapped_column(String(40), default="selected", nullable=False)
    module_code: Mapped[str] = mapped_column(String(80), nullable=False)
    module_name: Mapped[str] = mapped_column(String(255), nullable=False)
    offering_code: Mapped[str] = mapped_column(String(80), nullable=False)
    academic_period_label: Mapped[str] = mapped_column(String(180), nullable=False)
    qualification_level: Mapped[str | None] = mapped_column(String(100))
    delivery_mode: Mapped[str | None] = mapped_column(String(60))
    default_contact_hours: Mapped[int | None] = mapped_column(Integer)
    learning_outcomes: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    programme_context: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    module_attributes: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)


class OutputLifecycle(Base, UUIDPrimaryKeyMixin, TenantOwnedMixin, TimestampMixin):
    __tablename__ = "output_lifecycles"
    __table_args__ = (
        UniqueConstraint("tenant_id", "generated_output_id"),
        Index("ix_output_lifecycle_status", "tenant_id", "workflow_status"),
        {"schema": "conversation"},
    )

    generated_output_id: Mapped[UUID] = mapped_column(
        ForeignKey("conversation.generated_outputs.id"), nullable=False
    )
    owner_user_id: Mapped[UUID] = mapped_column(ForeignKey("iam.users.id"), nullable=False)
    module_id: Mapped[UUID | None] = mapped_column(ForeignKey("academic.modules.id"))
    module_offering_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("academic.module_offerings.id")
    )
    workflow_status: Mapped[str] = mapped_column(
        String(40), default=OutputWorkflowStatus.DRAFT.value, nullable=False
    )
    risk_level: Mapped[str] = mapped_column(
        String(30), default=AssessmentRiskLevel.NONE.value, nullable=False
    )
    assessment_kind: Mapped[str | None] = mapped_column(String(80))
    review_required: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    answer_key_present: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    student_release_allowed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    approved_by_user_id: Mapped[UUID | None] = mapped_column(ForeignKey("iam.users.id"))
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    released_by_user_id: Mapped[UUID | None] = mapped_column(ForeignKey("iam.users.id"))
    released_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    policy_snapshot: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)


class AssessmentSafetyReview(Base, UUIDPrimaryKeyMixin, TenantOwnedMixin, TimestampMixin):
    __tablename__ = "assessment_safety_reviews"
    __table_args__ = (
        UniqueConstraint("tenant_id", "output_version_id"),
        Index("ix_assessment_safety_output", "tenant_id", "generated_output_id"),
        {"schema": "review"},
    )

    generated_output_id: Mapped[UUID] = mapped_column(
        ForeignKey("conversation.generated_outputs.id"), nullable=False
    )
    output_version_id: Mapped[UUID] = mapped_column(
        ForeignKey("conversation.output_versions.id"), nullable=False
    )
    status: Mapped[str] = mapped_column(
        String(40), default=SafetyReviewStatus.REQUIRES_REVIEW.value, nullable=False
    )
    risk_level: Mapped[str] = mapped_column(
        String(30), default=AssessmentRiskLevel.NONE.value, nullable=False
    )
    checks: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    warnings: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    blocked_reasons: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    answers_detected: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    personal_data_detected: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    student_copy_safe: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    reviewed_by_user_id: Mapped[UUID | None] = mapped_column(ForeignKey("iam.users.id"))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    review_notes: Mapped[str | None] = mapped_column(Text)


class OutputWorkflowAction(Base, UUIDPrimaryKeyMixin, TenantOwnedMixin, TimestampMixin):
    __tablename__ = "output_workflow_actions"
    __table_args__ = (
        Index("ix_output_workflow_history", "tenant_id", "generated_output_id", "created_at"),
        {"schema": "conversation"},
    )

    generated_output_id: Mapped[UUID] = mapped_column(
        ForeignKey("conversation.generated_outputs.id"), nullable=False
    )
    output_version_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("conversation.output_versions.id")
    )
    action: Mapped[str] = mapped_column(String(60), nullable=False)
    previous_status: Mapped[str | None] = mapped_column(String(40))
    new_status: Mapped[str] = mapped_column(String(40), nullable=False)
    performed_by_user_id: Mapped[UUID] = mapped_column(ForeignKey("iam.users.id"), nullable=False)
    active_role_code: Mapped[str] = mapped_column(String(80), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    action_metadata: Mapped[dict] = mapped_column("metadata", JSONB, default=dict, nullable=False)


class ExportJob(Base, UUIDPrimaryKeyMixin, TenantOwnedMixin, TimestampMixin):
    __tablename__ = "export_jobs"
    __table_args__ = (
        Index("ix_export_requester", "tenant_id", "requested_by_user_id", "created_at"),
        {"schema": "content"},
    )

    generated_output_id: Mapped[UUID] = mapped_column(
        ForeignKey("conversation.generated_outputs.id"), nullable=False
    )
    output_version_id: Mapped[UUID] = mapped_column(
        ForeignKey("conversation.output_versions.id"), nullable=False
    )
    requested_by_user_id: Mapped[UUID] = mapped_column(ForeignKey("iam.users.id"), nullable=False)
    export_format: Mapped[str] = mapped_column(
        String(30), default=ExportFormat.DOCX.value, nullable=False
    )
    audience: Mapped[str] = mapped_column(
        String(40), default=ExportAudience.GENERIC.value, nullable=False
    )
    status: Mapped[str] = mapped_column(
        String(30), default=ExportStatus.REQUESTED.value, nullable=False
    )
    storage_object_id: Mapped[UUID | None] = mapped_column(ForeignKey("content.storage_objects.id"))
    safety_review_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("review.assessment_safety_reviews.id")
    )
    filename: Mapped[str | None] = mapped_column(String(500))
    media_type: Mapped[str | None] = mapped_column(String(150))
    size_bytes: Mapped[int | None] = mapped_column(Integer)
    generated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error_code: Mapped[str | None] = mapped_column(String(120))
    error_detail: Mapped[str | None] = mapped_column(Text)
    export_metadata: Mapped[dict] = mapped_column("metadata", JSONB, default=dict, nullable=False)
