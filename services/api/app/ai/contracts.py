from __future__ import annotations

from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, Field, HttpUrl


class TeachingTaskType(StrEnum):
    GENERIC_ANSWER = "generic_answer"
    LESSON_PLAN = "lesson_plan"
    PRACTICAL_LESSON = "practical_lesson"
    QUIZ = "quiz"
    TEST = "test"
    ASSIGNMENT = "assignment"
    EXAMINATION = "examination"
    RUBRIC = "rubric"
    MARKING_GUIDE = "marking_guide"
    CASE_STUDY = "case_study"
    TUTORIAL = "tutorial"
    MODERATION_REVIEW = "moderation_review"
    ALIGNMENT_REVIEW = "alignment_review"
    DEPARTMENTAL_ANALYSIS = "departmental_analysis"


class PrivacyClass(StrEnum):
    PUBLIC = "public"
    INTERNAL = "internal"
    CONFIDENTIAL = "confidential"
    RESTRICTED_ASSESSMENT = "restricted_assessment"


class ChatRole(StrEnum):
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"


class ChatMessage(BaseModel):
    role: ChatRole
    content: str = Field(min_length=1)


class TaskClassification(BaseModel):
    task_type: TeachingTaskType
    confidence: float = Field(ge=0, le=1)
    source_verification_required: bool = False
    institutional_context_required: bool = False
    human_review_required: bool = False
    privacy_classification: PrivacyClass = PrivacyClass.INTERNAL
    detected_entities: dict[str, Any] = Field(default_factory=dict)
    rationale_codes: list[str] = Field(default_factory=list)


class SourceCandidate(BaseModel):
    source_key: str
    source_type: str
    title: str
    authors: list[str] = Field(default_factory=list)
    publisher_or_organisation: str | None = None
    publication_date: str | None = None
    canonical_url: HttpUrl | None = None
    doi: str | None = None
    licence: str | None = None
    reliability_tier: str = "academic_metadata"
    retrieved_by: str
    retrieval_query: str
    rank: int | None = None
    relevance_score: float | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class ProviderRequest(BaseModel):
    messages: list[ChatMessage]
    system_prompt: str
    model: str
    max_output_tokens: int
    temperature: float
    structured_schema: dict[str, Any] | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class ProviderResponse(BaseModel):
    provider: str
    model: str
    text: str
    input_tokens: int | None = None
    output_tokens: int | None = None
    finish_reason: str | None = None
    latency_ms: int | None = None
    request_id: str | None = None
    provider_sources: list[SourceCandidate] = Field(default_factory=list)
    raw_metadata: dict[str, Any] = Field(default_factory=dict)


class ProviderAttempt(BaseModel):
    provider: str
    model: str
    status: Literal["completed", "failed", "skipped"]
    reason: str
    latency_ms: int | None = None
    error_code: str | None = None


class SourceCard(BaseModel):
    number: int
    source_key: str
    title: str
    authors: list[str] = Field(default_factory=list)
    publisher_or_organisation: str | None = None
    publication_date: str | None = None
    url: str | None = None
    doi: str | None = None
    verified_retrieval: bool = True
    cited_in_response: bool = False
    source_kind: str = "external"
    institutional: bool = False
    document_version_id: str | None = None
    locator: str | None = None
    access_label: str | None = None


class IntegrityResult(BaseModel):
    text: str
    cited_source_keys: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    removed_unverified_references: int = 0


class InlineOutput(BaseModel):
    output_type: TeachingTaskType
    title: str
    markdown: str
    editable: bool = True
    requires_human_review: bool = False
    approval_disclaimer: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
