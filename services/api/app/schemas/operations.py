from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from .common import ORMModel


class BackgroundJobCreate(BaseModel):
    job_type: str = Field(min_length=1, max_length=120)
    payload: dict = Field(default_factory=dict)
    queue_name: str = Field(default="default", min_length=1, max_length=80)
    priority: int = Field(default=100, ge=0, le=1000)
    max_attempts: int = Field(default=5, ge=1, le=20)
    idempotency_key: str | None = Field(default=None, max_length=240)


class BackgroundJobResponse(ORMModel):
    id: UUID
    tenant_id: UUID
    job_type: str
    queue_name: str
    status: str
    priority: int
    payload: dict
    result_payload: dict
    requested_by_user_id: UUID | None
    available_at: datetime
    attempt_count: int
    max_attempts: int
    completed_at: datetime | None
    last_error_code: str | None
    created_at: datetime
    updated_at: datetime


class JobRetryResponse(BaseModel):
    original_job_id: UUID
    replay_job: BackgroundJobResponse


class OperationsSummary(BaseModel):
    counts: dict[str, int]
    dead_letter_count: int
    oldest_queued_at: datetime | None


class BackupRunCreate(BaseModel):
    backup_type: str = Field(default="full", pattern="^(database|content|vectors|full)$")
    include_object_storage: bool = True
    include_vector_store: bool = True


class BackupRunResponse(ORMModel):
    id: UUID
    tenant_id: UUID
    backup_type: str
    status: str
    requested_by_user_id: UUID | None
    started_at: datetime | None
    completed_at: datetime | None
    storage_location: str | None
    manifest_sha256: str | None
    component_results: dict
    error_detail: str | None
    created_at: datetime
    updated_at: datetime


class RestoreDrillCreate(BaseModel):
    isolated_environment: str = Field(min_length=2, max_length=500)


class RestoreDrillResponse(ORMModel):
    id: UUID
    tenant_id: UUID
    backup_run_id: UUID
    status: str
    requested_by_user_id: UUID | None
    started_at: datetime | None
    completed_at: datetime | None
    isolated_environment: str | None
    validation_results: dict
    error_detail: str | None
    created_at: datetime
    updated_at: datetime


class ScheduledJobCreate(BaseModel):
    code: str = Field(min_length=2, max_length=120, pattern=r"^[a-z0-9_.-]+$")
    job_type: str = Field(min_length=1, max_length=120)
    interval_seconds: int = Field(ge=60, le=31_536_000)
    payload: dict = Field(default_factory=dict)
    is_enabled: bool = True


class ScheduledJobUpdate(BaseModel):
    interval_seconds: int | None = Field(default=None, ge=60, le=31_536_000)
    payload: dict | None = None
    is_enabled: bool | None = None


class ScheduledJobResponse(ORMModel):
    id: UUID
    tenant_id: UUID
    code: str
    job_type: str
    schedule_kind: str
    interval_seconds: int | None
    payload: dict
    is_enabled: bool
    next_run_at: datetime | None
    last_run_at: datetime | None
    created_by_user_id: UUID | None
    created_at: datetime
    updated_at: datetime


class NotificationDeliveryResponse(ORMModel):
    id: UUID
    tenant_id: UUID
    notification_id: UUID
    channel: str
    status: str
    attempt_count: int
    delivered_at: datetime | None
    provider_reference: str | None
    last_error_code: str | None
    last_error_detail: str | None
    delivery_metadata: dict
    created_at: datetime
    updated_at: datetime


class RetentionRunCreate(BaseModel):
    dry_run: bool = True
    max_candidates: int = Field(default=1000, ge=1, le=5000)


class RetentionRunResponse(ORMModel):
    id: UUID
    tenant_id: UUID
    requested_by_user_id: UUID | None
    status: str
    dry_run: bool
    evaluated_at: datetime | None
    completed_at: datetime | None
    candidate_count: int
    action_count: int
    skipped_count: int
    summary: dict
    error_detail: str | None
    created_at: datetime
    updated_at: datetime
