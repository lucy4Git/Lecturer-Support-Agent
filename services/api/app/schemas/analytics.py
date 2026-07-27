from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from .common import AuditFields

ScopeType = Literal["user", "organisational_unit", "programme", "module", "institution"]


class AnalyticsScope(BaseModel):
    scope_type: ScopeType
    scope_id: UUID | None = None


class MetricCard(BaseModel):
    key: str
    label: str
    value: int | float | str
    trend_percent: float | None = None
    status: str = "neutral"
    description: str | None = None


class SeriesPoint(BaseModel):
    label: str
    value: int | float


class AnalyticsOverviewResponse(BaseModel):
    scope: AnalyticsScope
    period_start: date
    period_end: date
    generated_at: datetime
    cards: list[MetricCard]
    output_mix: list[SeriesPoint]
    provider_mix: list[SeriesPoint]
    teaching_delivery: dict = Field(default_factory=dict)
    readiness: dict = Field(default_factory=dict)
    moderation: dict = Field(default_factory=dict)
    workload: dict = Field(default_factory=dict)
    alerts: list[dict] = Field(default_factory=list)
    data_notes: list[str] = Field(default_factory=list)


class AIUsageSummaryResponse(BaseModel):
    scope: AnalyticsScope
    period_start: date
    period_end: date
    request_count: int
    successful_count: int
    failed_count: int
    input_tokens: int
    output_tokens: int
    estimated_cost: Decimal
    currency_code: str
    average_latency_ms: float | None
    providers: list[dict]
    policy_status: dict


class AIUsagePolicyCreate(BaseModel):
    name: str = Field(min_length=3, max_length=200)
    scope_type: ScopeType = "institution"
    scope_id: UUID | None = None
    allowed_providers: list[str] = Field(default_factory=list, max_length=12)
    denied_providers: list[str] = Field(default_factory=list, max_length=12)
    local_only_privacy_classes: list[str] = Field(default_factory=lambda: ["confidential", "restricted_assessment"])
    source_required_for_tasks: list[str] = Field(default_factory=list)
    monthly_request_limit: int | None = Field(default=None, ge=1)
    monthly_input_token_limit: int | None = Field(default=None, ge=1)
    monthly_output_token_limit: int | None = Field(default=None, ge=1)
    monthly_cost_limit: Decimal | None = Field(default=None, ge=0)
    currency_code: str = Field(default="GBP", min_length=3, max_length=3)
    warning_threshold_percent: int = Field(default=80, ge=1, le=100)
    hard_limit_enabled: bool = False
    is_active: bool = True
    policy_metadata: dict = Field(default_factory=dict)

    @field_validator("allowed_providers", "denied_providers")
    @classmethod
    def normalise_providers(cls, value: list[str]) -> list[str]:
        allowed = {"openai", "anthropic", "google_gemini", "deepseek", "ollama", "development_mock"}
        cleaned = list(dict.fromkeys(item.strip().lower() for item in value if item.strip()))
        invalid = set(cleaned) - allowed
        if invalid:
            raise ValueError(f"Unsupported provider names: {', '.join(sorted(invalid))}")
        return cleaned


class AIUsagePolicyResponse(AuditFields):
    name: str
    scope_type: str
    scope_id: UUID | None
    allowed_providers: list
    denied_providers: list
    local_only_privacy_classes: list
    source_required_for_tasks: list
    monthly_request_limit: int | None
    monthly_input_token_limit: int | None
    monthly_output_token_limit: int | None
    monthly_cost_limit: Decimal | None
    currency_code: str
    warning_threshold_percent: int
    hard_limit_enabled: bool
    is_active: bool
    policy_metadata: dict


class ReportDefinitionCreate(BaseModel):
    code: str = Field(min_length=3, max_length=100, pattern=r"^[a-z0-9_\-]+$")
    name: str = Field(min_length=3, max_length=240)
    report_type: str = Field(min_length=3, max_length=100)
    description: str | None = Field(default=None, max_length=4000)
    default_scope_type: ScopeType = "institution"
    default_parameters: dict = Field(default_factory=dict)
    allowed_formats: list[str] = Field(default_factory=lambda: ["json", "csv", "pdf"])
    shared: bool = False


class ReportDefinitionResponse(AuditFields):
    code: str
    name: str
    report_type: str
    description: str | None
    default_scope_type: str
    default_parameters: dict
    allowed_formats: list
    owner_user_id: UUID
    shared: bool
    is_active: bool


class ReportRunCreate(BaseModel):
    report_definition_id: UUID | None = None
    report_type: str = Field(min_length=3, max_length=100)
    scope_type: ScopeType
    scope_id: UUID | None = None
    period_start: date | None = None
    period_end: date | None = None
    parameters: dict = Field(default_factory=dict)
    output_format: Literal["json", "csv", "pdf"] = "json"


class ReportRunResponse(AuditFields):
    report_definition_id: UUID | None
    report_type: str
    requested_by_user_id: UUID
    scope_type: str
    scope_id: UUID | None
    parameters: dict
    output_format: str
    status: str
    result_payload: dict
    result_sha256: str | None
    started_at: datetime | None
    completed_at: datetime | None
    expires_at: datetime | None
    error_code: str | None
    error_detail: str | None


class InsightAlertResponse(AuditFields):
    category: str
    severity: str
    status: str
    scope_type: str
    scope_id: UUID | None
    title: str
    message: str
    metric_key: str | None
    metric_value: Decimal | None
    threshold_value: Decimal | None
    action_path: str | None
    detected_at: datetime
    acknowledged_by_user_id: UUID | None
    acknowledged_at: datetime | None
    resolved_by_user_id: UUID | None
    resolved_at: datetime | None
    alert_metadata: dict


class AlertActionRequest(BaseModel):
    action: Literal["acknowledge", "resolve", "reopen"]


class AuditEventResponse(BaseModel):
    id: UUID
    occurred_at: datetime
    actor_user_id: UUID | None
    actor_role_code: str | None
    action: str
    resource_type: str
    resource_id: UUID | None
    correlation_id: str
    metadata: dict


class AuditSearchResponse(BaseModel):
    total: int
    events: list[AuditEventResponse]


class AuditExportCreate(BaseModel):
    start_at: datetime | None = None
    end_at: datetime | None = None
    actor_user_id: UUID | None = None
    action: str | None = Field(default=None, max_length=150)
    resource_type: str | None = Field(default=None, max_length=100)
    severity: str | None = Field(default=None, max_length=30)
    output_format: Literal["json", "csv"] = "json"


class AuditExportResponse(AuditFields):
    requested_by_user_id: UUID
    filters: dict
    output_format: str
    status: str
    record_count: int
    result_payload: dict
    result_sha256: str | None
    generated_at: datetime | None
    storage_object_id: UUID | None
    error_detail: str | None


class PlatformSettingUpsert(BaseModel):
    scope_type: ScopeType = "institution"
    scope_id: UUID | None = None
    value: dict
    value_type: Literal["string", "integer", "boolean", "json", "secret_reference"] = "json"
    description: str | None = Field(default=None, max_length=2000)


class PlatformSettingResponse(AuditFields):
    scope_type: str
    scope_id: UUID | None
    category: str
    setting_key: str
    value: dict
    value_type: str
    description: str | None
    secret_reference_only: bool
    locked: bool
    version_number: int
    updated_by_user_id: UUID
