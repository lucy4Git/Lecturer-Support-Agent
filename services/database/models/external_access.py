from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint, Uuid
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, TenantOwnedMixin, TimestampMixin, UUIDPrimaryKeyMixin
from .enums import ExternalGrantStatus, ReviewTaskStatus


class ExternalAccessGrant(Base, UUIDPrimaryKeyMixin, TenantOwnedMixin, TimestampMixin):
    __tablename__ = "external_access_grants"
    __table_args__ = (
        Index("ix_external_grant_active", "tenant_id", "external_user_id", "starts_at", "expires_at"),
        {"schema": "review"},
    )

    external_user_id: Mapped[UUID] = mapped_column(ForeignKey("iam.users.id"), nullable=False)
    granted_by_user_id: Mapped[UUID] = mapped_column(ForeignKey("iam.users.id"), nullable=False)
    purpose: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(
        String(30), default=ExternalGrantStatus.PENDING.value, nullable=False
    )
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_by_user_id: Mapped[UUID | None] = mapped_column(ForeignKey("iam.users.id"))
    allowed_actions: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    resource_scope: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)


class AccessInvitation(Base, UUIDPrimaryKeyMixin, TenantOwnedMixin, TimestampMixin):
    __tablename__ = "access_invitations"
    __table_args__ = (UniqueConstraint("tenant_id", "token_hash"), {"schema": "review"})

    external_access_grant_id: Mapped[UUID] = mapped_column(
        ForeignKey("review.external_access_grants.id"), nullable=False
    )
    email: Mapped[str] = mapped_column(String(320), nullable=False)
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AssignedReviewTask(Base, UUIDPrimaryKeyMixin, TenantOwnedMixin, TimestampMixin):
    __tablename__ = "assigned_review_tasks"
    __table_args__ = (
        Index("ix_review_assignee", "tenant_id", "assigned_user_id", "status"),
        Index("ix_review_task_cycle_round", "tenant_id", "review_cycle_id", "round_number"),
        {"schema": "review"},
    )

    assigned_user_id: Mapped[UUID] = mapped_column(ForeignKey("iam.users.id"), nullable=False)
    assigned_by_user_id: Mapped[UUID] = mapped_column(ForeignKey("iam.users.id"), nullable=False)
    external_access_grant_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("review.external_access_grants.id")
    )
    review_cycle_id: Mapped[UUID | None] = mapped_column(ForeignKey("review.review_cycles.id"))
    review_pack_id: Mapped[UUID | None] = mapped_column(ForeignKey("review.review_packs.id"))
    reviewer_role_code: Mapped[str | None] = mapped_column(String(80))
    review_kind: Mapped[str | None] = mapped_column(String(60))
    round_number: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    task_type: Mapped[str] = mapped_column(String(100), nullable=False)
    target_type: Mapped[str] = mapped_column(String(60), nullable=False)
    target_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    status: Mapped[str] = mapped_column(
        String(30), default=ReviewTaskStatus.ASSIGNED.value, nullable=False
    )
    due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    instructions: Mapped[str | None] = mapped_column(Text)
    permissions_snapshot: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    task_metadata: Mapped[dict] = mapped_column("metadata", JSONB, default=dict, nullable=False)


class AccessExpiryEvent(Base, UUIDPrimaryKeyMixin, TenantOwnedMixin, TimestampMixin):
    __tablename__ = "access_expiry_events"
    __table_args__ = (
        Index("ix_access_expiry_due", "tenant_id", "scheduled_for", "processed_at"),
        {"schema": "review"},
    )

    external_access_grant_id: Mapped[UUID] = mapped_column(
        ForeignKey("review.external_access_grants.id"), nullable=False
    )
    scheduled_for: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    outcome: Mapped[str | None] = mapped_column(String(100))
    details: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
