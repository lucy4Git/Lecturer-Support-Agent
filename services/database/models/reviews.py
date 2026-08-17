from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint, Uuid
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, TenantOwnedMixin, TimestampMixin, UUIDPrimaryKeyMixin
from .enums import (
    ReviewCorrectionStatus,
    ReviewCycleStatus,
    ReviewDecisionCode,
    ReviewFindingSeverity,
    ReviewFindingStatus,
    ReviewRecommendation,
)


class ReviewCycle(Base, UUIDPrimaryKeyMixin, TenantOwnedMixin, TimestampMixin):
    """One immutable moderation/external-review cycle for a generated output.

    A cycle may contain several review rounds. Each round targets an exact output
    version and receives its own sealed review pack and assignment set.
    """

    __tablename__ = "review_cycles"
    __table_args__ = (
        UniqueConstraint("tenant_id", "generated_output_id", "cycle_number"),
        Index("ix_review_cycle_status_due", "tenant_id", "status", "due_at"),
        Index("ix_review_cycle_module", "tenant_id", "module_offering_id", "created_at"),
        {"schema": "review"},
    )

    generated_output_id: Mapped[UUID] = mapped_column(
        ForeignKey("conversation.generated_outputs.id"), nullable=False
    )
    initiating_output_version_id: Mapped[UUID] = mapped_column(
        ForeignKey("conversation.output_versions.id"), nullable=False
    )
    module_offering_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("academic.module_offerings.id")
    )
    initiated_by_user_id: Mapped[UUID] = mapped_column(ForeignKey("iam.users.id"), nullable=False)
    review_kind: Mapped[str] = mapped_column(String(60), nullable=False)
    cycle_number: Mapped[int] = mapped_column(Integer, nullable=False)
    current_round: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    status: Mapped[str] = mapped_column(
        String(40), default=ReviewCycleStatus.ASSIGNED.value, nullable=False
    )
    due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    criteria_snapshot: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    policy_snapshot: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ReviewPack(Base, UUIDPrimaryKeyMixin, TenantOwnedMixin, TimestampMixin):
    __tablename__ = "review_packs"
    __table_args__ = (
        UniqueConstraint("tenant_id", "review_cycle_id", "round_number"),
        Index("ix_review_pack_cycle", "tenant_id", "review_cycle_id", "round_number"),
        {"schema": "review"},
    )

    review_cycle_id: Mapped[UUID] = mapped_column(
        ForeignKey("review.review_cycles.id"), nullable=False
    )
    round_number: Mapped[int] = mapped_column(Integer, nullable=False)
    created_by_user_id: Mapped[UUID] = mapped_column(ForeignKey("iam.users.id"), nullable=False)
    manifest: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    manifest_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    sealed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class ReviewPackItem(Base, UUIDPrimaryKeyMixin, TenantOwnedMixin, TimestampMixin):
    __tablename__ = "review_pack_items"
    __table_args__ = (
        Index("ix_review_pack_item_pack", "tenant_id", "review_pack_id", "created_at"),
        {"schema": "review"},
    )

    review_pack_id: Mapped[UUID] = mapped_column(ForeignKey("review.review_packs.id"), nullable=False)
    item_type: Mapped[str] = mapped_column(String(60), nullable=False)
    label: Mapped[str] = mapped_column(String(500), nullable=False)
    generated_output_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("conversation.generated_outputs.id")
    )
    output_version_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("conversation.output_versions.id")
    )
    document_version_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("content.document_versions.id")
    )
    export_job_id: Mapped[UUID | None] = mapped_column(ForeignKey("content.export_jobs.id"))
    required: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    checksum_sha256: Mapped[str | None] = mapped_column(String(64))
    item_metadata: Mapped[dict] = mapped_column("metadata", JSONB, default=dict, nullable=False)


class ReviewFinding(Base, UUIDPrimaryKeyMixin, TenantOwnedMixin, TimestampMixin):
    __tablename__ = "review_findings"
    __table_args__ = (
        Index("ix_review_finding_cycle_status", "tenant_id", "review_cycle_id", "status"),
        Index("ix_review_finding_task", "tenant_id", "review_task_id", "created_at"),
        {"schema": "review"},
    )

    review_cycle_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("review.review_cycles.id")
    )
    review_task_id: Mapped[UUID] = mapped_column(
        ForeignKey("review.assigned_review_tasks.id"), nullable=False
    )
    source_output_version_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("conversation.output_versions.id")
    )
    created_by_user_id: Mapped[UUID] = mapped_column(ForeignKey("iam.users.id"), nullable=False)
    criterion_code: Mapped[str | None] = mapped_column(String(120))
    category: Mapped[str] = mapped_column(String(100), nullable=False)
    severity: Mapped[str] = mapped_column(
        String(30), default=ReviewFindingSeverity.MEDIUM.value, nullable=False
    )
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    evidence_locator: Mapped[str | None] = mapped_column(String(500))
    recommendation: Mapped[str | None] = mapped_column(Text)
    is_blocking: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    status: Mapped[str] = mapped_column(
        String(30), default=ReviewFindingStatus.OPEN.value, nullable=False
    )
    finding_metadata: Mapped[dict] = mapped_column("metadata", JSONB, default=dict, nullable=False)


class ReviewFindingResponse(Base, UUIDPrimaryKeyMixin, TenantOwnedMixin, TimestampMixin):
    __tablename__ = "review_finding_responses"
    __table_args__ = (
        Index("ix_review_finding_response", "tenant_id", "review_finding_id", "created_at"),
        {"schema": "review"},
    )

    review_finding_id: Mapped[UUID] = mapped_column(
        ForeignKey("review.review_findings.id"), nullable=False
    )
    responded_by_user_id: Mapped[UUID] = mapped_column(ForeignKey("iam.users.id"), nullable=False)
    response_type: Mapped[str] = mapped_column(String(60), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    related_output_version_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("conversation.output_versions.id")
    )
    response_metadata: Mapped[dict] = mapped_column("metadata", JSONB, default=dict, nullable=False)


class ReviewSubmission(Base, UUIDPrimaryKeyMixin, TenantOwnedMixin, TimestampMixin):
    __tablename__ = "review_submissions"
    __table_args__ = (
        UniqueConstraint("tenant_id", "review_task_id", "submission_number"),
        Index("ix_review_submission_cycle", "tenant_id", "review_cycle_id", "round_number"),
        {"schema": "review"},
    )

    review_cycle_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("review.review_cycles.id")
    )
    review_task_id: Mapped[UUID] = mapped_column(
        ForeignKey("review.assigned_review_tasks.id"), nullable=False
    )
    reviewer_user_id: Mapped[UUID] = mapped_column(ForeignKey("iam.users.id"), nullable=False)
    round_number: Mapped[int] = mapped_column(Integer, nullable=False)
    submission_number: Mapped[int] = mapped_column(Integer, nullable=False)
    recommendation: Mapped[str] = mapped_column(
        String(50), default=ReviewRecommendation.CHANGES_REQUIRED.value, nullable=False
    )
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    criterion_assessments: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    declaration_accepted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    immutable_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    submitted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class ReviewDecision(Base, UUIDPrimaryKeyMixin, TenantOwnedMixin, TimestampMixin):
    __tablename__ = "review_decisions"
    __table_args__ = (
        UniqueConstraint("tenant_id", "review_cycle_id", "round_number"),
        Index("ix_review_decision_cycle", "tenant_id", "review_cycle_id", "round_number"),
        {"schema": "review"},
    )

    review_cycle_id: Mapped[UUID] = mapped_column(
        ForeignKey("review.review_cycles.id"), nullable=False
    )
    round_number: Mapped[int] = mapped_column(Integer, nullable=False)
    decided_by_user_id: Mapped[UUID] = mapped_column(ForeignKey("iam.users.id"), nullable=False)
    decision: Mapped[str] = mapped_column(
        String(50), default=ReviewDecisionCode.CHANGES_REQUIRED.value, nullable=False
    )
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    conditions: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    linked_submission_ids: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    decided_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    superseded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ReviewCorrectionRound(Base, UUIDPrimaryKeyMixin, TenantOwnedMixin, TimestampMixin):
    __tablename__ = "review_correction_rounds"
    __table_args__ = (
        UniqueConstraint("tenant_id", "review_cycle_id", "round_number"),
        Index("ix_review_correction_cycle", "tenant_id", "review_cycle_id", "status"),
        {"schema": "review"},
    )

    review_cycle_id: Mapped[UUID] = mapped_column(
        ForeignKey("review.review_cycles.id"), nullable=False
    )
    round_number: Mapped[int] = mapped_column(Integer, nullable=False)
    requested_by_user_id: Mapped[UUID] = mapped_column(ForeignKey("iam.users.id"), nullable=False)
    source_output_version_id: Mapped[UUID] = mapped_column(
        ForeignKey("conversation.output_versions.id"), nullable=False
    )
    corrected_output_version_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("conversation.output_versions.id")
    )
    status: Mapped[str] = mapped_column(
        String(40), default=ReviewCorrectionStatus.REQUESTED.value, nullable=False
    )
    due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    resubmitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    resolution_summary: Mapped[str | None] = mapped_column(Text)
    finding_ids: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
