from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, TenantOwnedMixin, TimestampMixin, UUIDPrimaryKeyMixin


class PlatformSetting(Base, UUIDPrimaryKeyMixin, TenantOwnedMixin, TimestampMixin):
    """Versioned, non-secret commercial platform configuration.

    Secret values are never stored here. A secret-backed setting may only store
    the name of an environment variable or secret-manager reference.
    """

    __tablename__ = "platform_settings"
    __table_args__ = (
        Index(
            "uq_platform_setting_scope_key",
            "tenant_id",
            "scope_type",
            "scope_id",
            "category",
            "setting_key",
            unique=True,
            postgresql_nulls_not_distinct=True,
        ),
        Index("ix_platform_setting_category", "tenant_id", "category", "setting_key"),
        {"schema": "governance"},
    )

    scope_type: Mapped[str] = mapped_column(String(40), default="institution", nullable=False)
    scope_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True))
    category: Mapped[str] = mapped_column(String(80), nullable=False)
    setting_key: Mapped[str] = mapped_column(String(120), nullable=False)
    value: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    value_type: Mapped[str] = mapped_column(String(30), default="json", nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    secret_reference_only: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    locked: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    version_number: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    updated_by_user_id: Mapped[UUID] = mapped_column(ForeignKey("iam.users.id"), nullable=False)


class AIUsagePolicy(Base, UUIDPrimaryKeyMixin, TenantOwnedMixin, TimestampMixin):
    """Institution or scoped policy governing provider use and monthly limits."""

    __tablename__ = "ai_usage_policies"
    __table_args__ = (
        Index("ix_ai_usage_policy_scope", "tenant_id", "scope_type", "scope_id", "is_active"),
        {"schema": "governance"},
    )

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    scope_type: Mapped[str] = mapped_column(String(40), default="institution", nullable=False)
    scope_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True))
    allowed_providers: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    denied_providers: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    local_only_privacy_classes: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    source_required_for_tasks: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    monthly_request_limit: Mapped[int | None] = mapped_column(Integer)
    monthly_input_token_limit: Mapped[int | None] = mapped_column(Integer)
    monthly_output_token_limit: Mapped[int | None] = mapped_column(Integer)
    monthly_cost_limit: Mapped[Decimal | None] = mapped_column(Numeric(14, 4))
    currency_code: Mapped[str] = mapped_column(String(3), default="GBP", nullable=False)
    warning_threshold_percent: Mapped[int] = mapped_column(Integer, default=80, nullable=False)
    hard_limit_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    policy_metadata: Mapped[dict] = mapped_column("metadata", JSONB, default=dict, nullable=False)
    created_by_user_id: Mapped[UUID] = mapped_column(ForeignKey("iam.users.id"), nullable=False)


class AIUsageDaily(Base, UUIDPrimaryKeyMixin, TenantOwnedMixin, TimestampMixin):
    """Daily usage ledger used for governed limits and operational reporting."""

    __tablename__ = "ai_usage_daily"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "usage_date",
            "user_id",
            "provider",
            "model_id",
            "role_code",
            "task_type",
        ),
        Index("ix_ai_usage_daily_period", "tenant_id", "usage_date", "provider"),
        {"schema": "analytics"},
    )

    usage_date: Mapped[date] = mapped_column(Date, nullable=False)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("iam.users.id"), nullable=False)
    provider: Mapped[str] = mapped_column(String(60), nullable=False)
    model_id: Mapped[str] = mapped_column(String(160), nullable=False)
    role_code: Mapped[str] = mapped_column(String(80), nullable=False)
    task_type: Mapped[str] = mapped_column(String(120), nullable=False)
    request_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    successful_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    failed_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    input_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    estimated_cost: Mapped[Decimal] = mapped_column(Numeric(14, 4), default=0, nullable=False)
    currency_code: Mapped[str] = mapped_column(String(3), default="GBP", nullable=False)
    latency_total_ms: Mapped[int] = mapped_column(Integer, default=0, nullable=False)


class AnalyticsSnapshot(Base, UUIDPrimaryKeyMixin, TenantOwnedMixin, TimestampMixin):
    __tablename__ = "analytics_snapshots"
    __table_args__ = (
        Index("ix_analytics_snapshot_scope", "tenant_id", "scope_type", "scope_id", "generated_at"),
        {"schema": "analytics"},
    )

    snapshot_type: Mapped[str] = mapped_column(String(100), nullable=False)
    scope_type: Mapped[str] = mapped_column(String(40), nullable=False)
    scope_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True))
    period_start: Mapped[date] = mapped_column(Date, nullable=False)
    period_end: Mapped[date] = mapped_column(Date, nullable=False)
    metrics: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    source_watermark: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    generated_by_user_id: Mapped[UUID] = mapped_column(ForeignKey("iam.users.id"), nullable=False)
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class ReportDefinition(Base, UUIDPrimaryKeyMixin, TenantOwnedMixin, TimestampMixin):
    __tablename__ = "report_definitions"
    __table_args__ = (
        UniqueConstraint("tenant_id", "code"),
        Index("ix_report_definition_type", "tenant_id", "report_type", "is_active"),
        {"schema": "analytics"},
    )

    code: Mapped[str] = mapped_column(String(100), nullable=False)
    name: Mapped[str] = mapped_column(String(240), nullable=False)
    report_type: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    default_scope_type: Mapped[str] = mapped_column(String(40), default="institution", nullable=False)
    default_parameters: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    allowed_formats: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    owner_user_id: Mapped[UUID] = mapped_column(ForeignKey("iam.users.id"), nullable=False)
    shared: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class ReportRun(Base, UUIDPrimaryKeyMixin, TenantOwnedMixin, TimestampMixin):
    __tablename__ = "report_runs"
    __table_args__ = (
        Index("ix_report_run_requester", "tenant_id", "requested_by_user_id", "created_at"),
        Index("ix_report_run_status", "tenant_id", "status", "created_at"),
        {"schema": "analytics"},
    )

    report_definition_id: Mapped[UUID | None] = mapped_column(ForeignKey("analytics.report_definitions.id"))
    report_type: Mapped[str] = mapped_column(String(100), nullable=False)
    requested_by_user_id: Mapped[UUID] = mapped_column(ForeignKey("iam.users.id"), nullable=False)
    scope_type: Mapped[str] = mapped_column(String(40), nullable=False)
    scope_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True))
    parameters: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    output_format: Mapped[str] = mapped_column(String(30), default="json", nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="requested", nullable=False)
    result_payload: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    result_sha256: Mapped[str | None] = mapped_column(String(64))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error_code: Mapped[str | None] = mapped_column(String(120))
    error_detail: Mapped[str | None] = mapped_column(Text)


class InsightAlert(Base, UUIDPrimaryKeyMixin, TenantOwnedMixin, TimestampMixin):
    __tablename__ = "insight_alerts"
    __table_args__ = (
        Index("ix_insight_alert_status", "tenant_id", "status", "severity", "detected_at"),
        {"schema": "analytics"},
    )

    category: Mapped[str] = mapped_column(String(100), nullable=False)
    severity: Mapped[str] = mapped_column(String(30), nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="open", nullable=False)
    scope_type: Mapped[str] = mapped_column(String(40), nullable=False)
    scope_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True))
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    metric_key: Mapped[str | None] = mapped_column(String(120))
    metric_value: Mapped[Decimal | None] = mapped_column(Numeric(14, 4))
    threshold_value: Mapped[Decimal | None] = mapped_column(Numeric(14, 4))
    action_path: Mapped[str | None] = mapped_column(String(1024))
    detected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    acknowledged_by_user_id: Mapped[UUID | None] = mapped_column(ForeignKey("iam.users.id"))
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    resolved_by_user_id: Mapped[UUID | None] = mapped_column(ForeignKey("iam.users.id"))
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    alert_metadata: Mapped[dict] = mapped_column("metadata", JSONB, default=dict, nullable=False)


class AuditExportJob(Base, UUIDPrimaryKeyMixin, TenantOwnedMixin, TimestampMixin):
    __tablename__ = "audit_export_jobs"
    __table_args__ = (
        Index("ix_audit_export_requester", "tenant_id", "requested_by_user_id", "created_at"),
        {"schema": "audit"},
    )

    requested_by_user_id: Mapped[UUID] = mapped_column(ForeignKey("iam.users.id"), nullable=False)
    filters: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    output_format: Mapped[str] = mapped_column(String(30), default="json", nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="requested", nullable=False)
    record_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    result_payload: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    result_sha256: Mapped[str | None] = mapped_column(String(64))
    generated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    storage_object_id: Mapped[UUID | None] = mapped_column(ForeignKey("content.storage_objects.id"))
    error_detail: Mapped[str | None] = mapped_column(Text)
