from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from .common import AuditFields


class ModuleContextRead(BaseModel):
    module_id: UUID
    module_offering_id: UUID
    module_code: str
    module_name: str
    offering_code: str
    academic_period: str
    qualification_level: str | None = None
    delivery_mode: str | None = None
    default_contact_hours: int | None = None
    learning_outcomes: list[dict] = Field(default_factory=list)
    programmes: list[dict] = Field(default_factory=list)
    module_attributes: dict = Field(default_factory=dict)


class OutputVersionCreate(BaseModel):
    content_markdown: str = Field(min_length=1, max_length=500_000)
    change_reason: str = Field(min_length=3, max_length=1000)


class OutputVersionRead(AuditFields):
    generated_output_id: UUID
    version_number: int
    previous_version_id: UUID | None
    created_by_user_id: UUID | None
    model_execution_id: UUID | None
    content_text: str
    structured_content: dict
    change_reason: str


class SafetyReviewRead(AuditFields):
    generated_output_id: UUID
    output_version_id: UUID
    status: str
    risk_level: str
    checks: list
    warnings: list
    blocked_reasons: list
    answers_detected: bool
    personal_data_detected: bool
    student_copy_safe: bool
    reviewed_by_user_id: UUID | None
    reviewed_at: datetime | None
    review_notes: str | None


class OutputLifecycleRead(AuditFields):
    generated_output_id: UUID
    owner_user_id: UUID
    module_id: UUID | None
    module_offering_id: UUID | None
    workflow_status: str
    risk_level: str
    assessment_kind: str | None
    review_required: bool
    answer_key_present: bool
    student_release_allowed: bool
    approved_by_user_id: UUID | None
    approved_at: datetime | None
    released_by_user_id: UUID | None
    released_at: datetime | None
    archived_at: datetime | None
    policy_snapshot: dict


class TeachingOutputRead(BaseModel):
    id: UUID
    conversation_id: UUID
    source_message_id: UUID
    output_type: str
    title: str
    current_version_id: UUID
    is_formally_approved: bool
    approval_disclaimer: str | None
    lifecycle: OutputLifecycleRead
    current_version: OutputVersionRead
    safety_review: SafetyReviewRead


class RestoreVersionRequest(BaseModel):
    change_reason: str = Field(min_length=3, max_length=1000)


class WorkflowTransitionRequest(BaseModel):
    action: str = Field(pattern="^(submit_for_review|request_changes|approve|reject|release|archive|return_to_draft)$")
    reason: str = Field(min_length=3, max_length=2000)


class WorkflowActionRead(AuditFields):
    generated_output_id: UUID
    output_version_id: UUID | None
    action: str
    previous_status: str | None
    new_status: str
    performed_by_user_id: UUID
    active_role_code: str
    reason: str
    action_metadata: dict


class ExportCreate(BaseModel):
    export_format: str = Field(pattern="^(markdown|html|docx|pdf|pptx|xlsx)$")
    audience: str = Field(default="generic", pattern="^(generic|lecturer_pack|student_copy|moderation_pack)$")
    version_id: UUID | None = None


class ExportJobRead(AuditFields):
    generated_output_id: UUID
    output_version_id: UUID
    requested_by_user_id: UUID
    export_format: str
    audience: str
    status: str
    storage_object_id: UUID | None
    safety_review_id: UUID | None
    filename: str | None
    media_type: str | None
    size_bytes: int | None
    generated_at: datetime | None
    error_code: str | None
    error_detail: str | None
    export_metadata: dict
    download_path: str | None = None
