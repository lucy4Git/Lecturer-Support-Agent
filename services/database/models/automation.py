from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint, Uuid
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, TenantOwnedMixin, TimestampMixin, UUIDPrimaryKeyMixin


class NotificationDelivery(Base, UUIDPrimaryKeyMixin, TenantOwnedMixin, TimestampMixin):
    """Durable delivery evidence for one notification and one channel."""

    __tablename__ = "notification_deliveries"
    __table_args__ = (
        UniqueConstraint("tenant_id", "notification_id", "channel", name="uq_notification_delivery_channel"),
        Index("ix_notification_delivery_status", "tenant_id", "status", "created_at"),
        {"schema": "governance"},
    )

    notification_id: Mapped[UUID] = mapped_column(
        ForeignKey("governance.notifications.id", ondelete="CASCADE"), nullable=False
    )
    channel: Mapped[str] = mapped_column(String(40), default="in_app", nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="pending", nullable=False)
    attempt_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    provider_reference: Mapped[str | None] = mapped_column(String(500))
    last_error_code: Mapped[str | None] = mapped_column(String(120))
    last_error_detail: Mapped[str | None] = mapped_column(Text)
    delivery_metadata: Mapped[dict] = mapped_column("metadata", JSONB, default=dict, nullable=False)


class RetentionRun(Base, UUIDPrimaryKeyMixin, TenantOwnedMixin, TimestampMixin):
    """One governed retention evaluation; destructive deletion is never implicit."""

    __tablename__ = "retention_runs"
    __table_args__ = (
        Index("ix_retention_run_status", "tenant_id", "status", "created_at"),
        {"schema": "privacy"},
    )

    requested_by_user_id: Mapped[UUID | None] = mapped_column(ForeignKey("iam.users.id"))
    status: Mapped[str] = mapped_column(String(30), default="requested", nullable=False)
    dry_run: Mapped[bool] = mapped_column(default=True, nullable=False)
    evaluated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    candidate_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    action_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    skipped_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    summary: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    error_detail: Mapped[str | None] = mapped_column(Text)


class RetentionRunItem(Base, UUIDPrimaryKeyMixin, TenantOwnedMixin, TimestampMixin):
    """Evidence for an evaluated retention candidate and its safe disposition."""

    __tablename__ = "retention_run_items"
    __table_args__ = (
        Index("ix_retention_item_run", "tenant_id", "retention_run_id", "status"),
        Index("ix_retention_item_resource", "tenant_id", "resource_type", "resource_id"),
        {"schema": "privacy"},
    )

    retention_run_id: Mapped[UUID] = mapped_column(
        ForeignKey("privacy.retention_runs.id", ondelete="CASCADE"), nullable=False
    )
    retention_rule_id: Mapped[UUID | None] = mapped_column(ForeignKey("privacy.retention_rules.id"))
    resource_type: Mapped[str] = mapped_column(String(120), nullable=False)
    resource_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    disposition_action: Mapped[str] = mapped_column(String(80), nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="planned", nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    evaluated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    applied_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    item_metadata: Mapped[dict] = mapped_column("metadata", JSONB, default=dict, nullable=False)
