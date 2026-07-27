from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, String, Text, UniqueConstraint, Uuid
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, TenantOwnedMixin, TimestampMixin, UUIDPrimaryKeyMixin


class SavedOutput(Base, UUIDPrimaryKeyMixin, TenantOwnedMixin, TimestampMixin):
    """A user's durable pointer to one immutable generated-output version."""

    __tablename__ = "saved_outputs"
    __table_args__ = (
        UniqueConstraint("tenant_id", "user_id", "output_version_id"),
        Index("ix_saved_output_user_updated", "tenant_id", "user_id", "updated_at"),
        {"schema": "conversation"},
    )

    user_id: Mapped[UUID] = mapped_column(ForeignKey("iam.users.id"), nullable=False)
    generated_output_id: Mapped[UUID] = mapped_column(
        ForeignKey("conversation.generated_outputs.id", ondelete="CASCADE"), nullable=False
    )
    output_version_id: Mapped[UUID] = mapped_column(
        ForeignKey("conversation.output_versions.id", ondelete="RESTRICT"), nullable=False
    )
    label: Mapped[str | None] = mapped_column(String(300))
    note: Mapped[str | None] = mapped_column(Text)
    folder: Mapped[str | None] = mapped_column(String(160))
    tags: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    is_pinned: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


class Notification(Base, UUIDPrimaryKeyMixin, TenantOwnedMixin, TimestampMixin):
    """Actionable, auditable notification delivered to one institutional user."""

    __tablename__ = "notifications"
    __table_args__ = (
        Index(
            "ix_notification_recipient_unread",
            "tenant_id",
            "recipient_user_id",
            "read_at",
            "created_at",
        ),
        Index("ix_notification_resource", "tenant_id", "resource_type", "resource_id"),
        {"schema": "governance"},
    )

    recipient_user_id: Mapped[UUID] = mapped_column(ForeignKey("iam.users.id"), nullable=False)
    notification_type: Mapped[str] = mapped_column(String(100), nullable=False)
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    severity: Mapped[str] = mapped_column(String(30), default="information", nullable=False)
    action_path: Mapped[str | None] = mapped_column(String(1024))
    resource_type: Mapped[str | None] = mapped_column(String(80))
    resource_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True))
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    notification_metadata: Mapped[dict] = mapped_column("metadata", JSONB, default=dict, nullable=False)
