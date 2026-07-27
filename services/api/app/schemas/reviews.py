from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from .common import AuditFields


class ReviewAssigneeCreate(BaseModel):
    user_id: UUID
    reviewer_role_code: str = Field(
        pattern="^(internal_moderator|external_moderator|external_reviewer)$"
    )
    external_access_grant_id: UUID | None = None

    @model_validator(mode="after")
    def external_grant_required(self) -> "ReviewAssigneeCreate":
        if self.reviewer_role_code.startswith("external_") and self.external_access_grant_id is None:
            raise ValueError("External reviewers and moderators require a scoped access grant")
        return self


class ReviewCycleCreate(BaseModel):
    generated_output_id: UUID
    review_kind: str = Field(
        pattern="^(internal_moderation|external_moderation|external_review|quality_review)$"
    )
    due_at: datetime | None = None
    instructions: str = Field(min_length=3, max_length=5000)
    criteria: list[str] = Field(min_length=1, max_length=50)
    assignees: list[ReviewAssigneeCreate] = Field(min_length=1, max_length=20)
    supporting_document_version_ids: list[UUID] = Field(default_factory=list, max_length=100)
    supporting_export_ids: list[UUID] = Field(default_factory=list, max_length=50)


class ReviewPackItemRead(AuditFields):
    review_pack_id: UUID
    item_type: str
    label: str
    generated_output_id: UUID | None
    output_version_id: UUID | None
    document_version_id: UUID | None
    export_job_id: UUID | None
    required: bool
    checksum_sha256: str | None
    item_metadata: dict


class ReviewTaskRead(AuditFields):
    assigned_user_id: UUID
    assigned_by_user_id: UUID
    external_access_grant_id: UUID | None
    review_cycle_id: UUID | None
    review_pack_id: UUID | None
    reviewer_role_code: str | None
    review_kind: str | None
    round_number: int
    task_type: str
    target_type: str
    target_id: UUID
    status: str
    due_at: datetime | None
    accepted_at: datetime | None
    started_at: datetime | None
    submitted_at: datetime | None
    completed_at: datetime | None
    instructions: str | None
    permissions_snapshot: dict
    task_metadata: dict


class ReviewCycleRead(AuditFields):
    generated_output_id: UUID
    initiating_output_version_id: UUID
    module_offering_id: UUID | None
    initiated_by_user_id: UUID
    review_kind: str
    cycle_number: int
    current_round: int
    status: str
    due_at: datetime | None
    criteria_snapshot: list
    policy_snapshot: dict
    started_at: datetime | None
    completed_at: datetime | None
    closed_at: datetime | None
    tasks: list[ReviewTaskRead] = Field(default_factory=list)
    pack_items: list[ReviewPackItemRead] = Field(default_factory=list)
    open_findings: int = 0
    blocking_findings: int = 0


class ReviewTaskActionRequest(BaseModel):
    reason: str = Field(min_length=3, max_length=2000)


class ReviewFindingCreate(BaseModel):
    criterion_code: str | None = Field(default=None, max_length=120)
    category: str = Field(min_length=2, max_length=100)
    severity: str = Field(pattern="^(info|low|medium|high|critical)$")
    title: str = Field(min_length=3, max_length=500)
    description: str = Field(min_length=3, max_length=10_000)
    evidence_locator: str | None = Field(default=None, max_length=500)
    recommendation: str | None = Field(default=None, max_length=5000)
    is_blocking: bool = False
    metadata: dict = Field(default_factory=dict)


class ReviewFindingUpdate(BaseModel):
    severity: str | None = Field(default=None, pattern="^(info|low|medium|high|critical)$")
    title: str | None = Field(default=None, min_length=3, max_length=500)
    description: str | None = Field(default=None, min_length=3, max_length=10_000)
    evidence_locator: str | None = Field(default=None, max_length=500)
    recommendation: str | None = Field(default=None, max_length=5000)
    is_blocking: bool | None = None
    status: str | None = Field(default=None, pattern="^(open|responded|resolved|accepted|disputed|withdrawn)$")


class ReviewFindingRead(AuditFields):
    review_cycle_id: UUID
    review_task_id: UUID
    source_output_version_id: UUID
    created_by_user_id: UUID
    criterion_code: str | None
    category: str
    severity: str
    title: str
    description: str
    evidence_locator: str | None
    recommendation: str | None
    is_blocking: bool
    status: str
    finding_metadata: dict


class ReviewFindingResponseCreate(BaseModel):
    response_type: str = Field(
        pattern="^(acknowledgement|action_plan|resolution_evidence|dispute|clarification)$"
    )
    body: str = Field(min_length=3, max_length=10_000)
    related_output_version_id: UUID | None = None
    metadata: dict = Field(default_factory=dict)


class ReviewFindingResponseRead(AuditFields):
    review_finding_id: UUID
    responded_by_user_id: UUID
    response_type: str
    body: str
    related_output_version_id: UUID | None
    response_metadata: dict


class ReviewSubmissionCreate(BaseModel):
    recommendation: str = Field(
        pattern="^(approve|approve_with_conditions|changes_required|reject)$"
    )
    summary: str = Field(min_length=10, max_length=20_000)
    criterion_assessments: list[dict] = Field(min_length=1, max_length=100)
    declaration_accepted: bool

    @model_validator(mode="after")
    def declaration_is_required(self) -> "ReviewSubmissionCreate":
        if not self.declaration_accepted:
            raise ValueError("The reviewer declaration must be accepted before submission")
        return self


class ReviewSubmissionRead(AuditFields):
    review_cycle_id: UUID
    review_task_id: UUID
    reviewer_user_id: UUID
    round_number: int
    submission_number: int
    recommendation: str
    summary: str
    criterion_assessments: list
    declaration_accepted: bool
    immutable_sha256: str
    submitted_at: datetime


class ReviewDecisionCreate(BaseModel):
    decision: str = Field(
        pattern="^(approved|approved_with_conditions|changes_required|rejected)$"
    )
    reason: str = Field(min_length=5, max_length=20_000)
    conditions: list[str] = Field(default_factory=list, max_length=100)
    correction_due_at: datetime | None = None


class ReviewDecisionRead(AuditFields):
    review_cycle_id: UUID
    round_number: int
    decided_by_user_id: UUID
    decision: str
    reason: str
    conditions: list
    linked_submission_ids: list
    decided_at: datetime
    superseded_at: datetime | None


class CorrectionResubmissionCreate(BaseModel):
    corrected_output_version_id: UUID
    resolution_summary: str = Field(min_length=10, max_length=20_000)


class DepartmentReviewDashboardRead(BaseModel):
    organisational_unit_id: UUID
    active_cycles: int
    decision_pending_cycles: int
    overdue_cycles: int
    assigned_tasks: int
    in_progress_tasks: int
    submitted_tasks: int
    open_findings: int
    blocking_findings: int
