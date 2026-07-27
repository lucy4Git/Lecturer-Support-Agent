from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint, Uuid
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, TenantOwnedMixin, TimestampMixin, UUIDPrimaryKeyMixin


class BackgroundJob(Base, UUIDPrimaryKeyMixin, TenantOwnedMixin, TimestampMixin):
    """Durable tenant-scoped work item claimed with a database lease."""

    __tablename__ = "background_jobs"
    __table_args__ = (
        UniqueConstraint("tenant_id", "idempotency_key", name="uq_background_job_idempotency"),
        Index("ix_background_job_claim", "status", "available_at", "priority", "created_at"),
        Index("ix_background_job_tenant_type", "tenant_id", "job_type", "status"),
        {"schema": "operations"},
    )

    job_type: Mapped[str] = mapped_column(String(120), nullable=False)
    queue_name: Mapped[str] = mapped_column(String(80), default="default", nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="queued", nullable=False)
    priority: Mapped[int] = mapped_column(Integer, default=100, nullable=False)
    payload: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    result_payload: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    idempotency_key: Mapped[str | None] = mapped_column(String(240))
    correlation_id: Mapped[str | None] = mapped_column(String(100))
    requested_by_user_id: Mapped[UUID | None] = mapped_column(ForeignKey("iam.users.id"))
    available_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    locked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    locked_by: Mapped[str | None] = mapped_column(String(160))
    lease_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    attempt_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    max_attempts: Mapped[int] = mapped_column(Integer, default=5, nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error_code: Mapped[str | None] = mapped_column(String(120))
    last_error_detail: Mapped[str | None] = mapped_column(Text)


class BackgroundJobAttempt(Base, UUIDPrimaryKeyMixin, TenantOwnedMixin, TimestampMixin):
    __tablename__ = "background_job_attempts"
    __table_args__ = (
        UniqueConstraint("tenant_id", "job_id", "attempt_number"),
        Index("ix_background_job_attempt_job", "tenant_id", "job_id", "attempt_number"),
        {"schema": "operations"},
    )

    job_id: Mapped[UUID] = mapped_column(ForeignKey("operations.background_jobs.id", ondelete="CASCADE"), nullable=False)
    attempt_number: Mapped[int] = mapped_column(Integer, nullable=False)
    worker_id: Mapped[str] = mapped_column(String(160), nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="running", nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error_code: Mapped[str | None] = mapped_column(String(120))
    error_detail: Mapped[str | None] = mapped_column(Text)
    metrics: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)


class DeadLetterJob(Base, UUIDPrimaryKeyMixin, TenantOwnedMixin, TimestampMixin):
    __tablename__ = "dead_letter_jobs"
    __table_args__ = (
        UniqueConstraint("tenant_id", "original_job_id"),
        Index("ix_dead_letter_failed", "tenant_id", "failed_at"),
        {"schema": "operations"},
    )

    original_job_id: Mapped[UUID] = mapped_column(ForeignKey("operations.background_jobs.id"), nullable=False)
    job_type: Mapped[str] = mapped_column(String(120), nullable=False)
    payload: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    failed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    failure_reason: Mapped[str] = mapped_column(Text, nullable=False)
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False)
    replayed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    replayed_by_user_id: Mapped[UUID | None] = mapped_column(ForeignKey("iam.users.id"))
    replay_job_id: Mapped[UUID | None] = mapped_column(ForeignKey("operations.background_jobs.id"))


class ScheduledJob(Base, UUIDPrimaryKeyMixin, TenantOwnedMixin, TimestampMixin):
    __tablename__ = "scheduled_jobs"
    __table_args__ = (
        UniqueConstraint("tenant_id", "code"),
        Index("ix_scheduled_job_due", "is_enabled", "next_run_at"),
        {"schema": "operations"},
    )

    code: Mapped[str] = mapped_column(String(120), nullable=False)
    job_type: Mapped[str] = mapped_column(String(120), nullable=False)
    schedule_kind: Mapped[str] = mapped_column(String(30), default="interval", nullable=False)
    interval_seconds: Mapped[int | None] = mapped_column(Integer)
    cron_expression: Mapped[str | None] = mapped_column(String(160))
    payload: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    next_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_by_user_id: Mapped[UUID | None] = mapped_column(ForeignKey("iam.users.id"))


class BackupRun(Base, UUIDPrimaryKeyMixin, TenantOwnedMixin, TimestampMixin):
    __tablename__ = "backup_runs"
    __table_args__ = (
        Index("ix_backup_run_status", "tenant_id", "status", "created_at"),
        {"schema": "operations"},
    )

    backup_type: Mapped[str] = mapped_column(String(60), nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="requested", nullable=False)
    requested_by_user_id: Mapped[UUID | None] = mapped_column(ForeignKey("iam.users.id"))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    storage_location: Mapped[str | None] = mapped_column(String(1200))
    manifest_sha256: Mapped[str | None] = mapped_column(String(64))
    component_results: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    error_detail: Mapped[str | None] = mapped_column(Text)


class RestoreDrill(Base, UUIDPrimaryKeyMixin, TenantOwnedMixin, TimestampMixin):
    __tablename__ = "restore_drills"
    __table_args__ = (
        Index("ix_restore_drill_status", "tenant_id", "status", "created_at"),
        {"schema": "operations"},
    )

    backup_run_id: Mapped[UUID] = mapped_column(ForeignKey("operations.backup_runs.id"), nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="requested", nullable=False)
    requested_by_user_id: Mapped[UUID | None] = mapped_column(ForeignKey("iam.users.id"))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    isolated_environment: Mapped[str | None] = mapped_column(String(500))
    validation_results: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    error_detail: Mapped[str | None] = mapped_column(Text)
