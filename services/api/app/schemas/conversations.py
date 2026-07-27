from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from ..ai.contracts import InlineOutput, SourceCard, TaskClassification
from .common import AuditFields


class ConversationCreate(BaseModel):
    title: str | None = Field(default=None, max_length=300)
    org_unit_id: UUID | None = None
    programme_id: UUID | None = None
    module_id: UUID | None = None
    context: dict = Field(default_factory=dict)


class ConversationRead(AuditFields):
    owner_user_id: UUID
    title: str
    org_unit_id: UUID | None
    programme_id: UUID | None
    module_id: UUID | None
    is_archived: bool
    context: dict


class MessageCreate(BaseModel):
    content: str = Field(min_length=1, max_length=100_000)
    attachment_version_ids: list[UUID] = Field(default_factory=list, max_length=20)
    institutional_context: str | None = Field(default=None, max_length=100_000)
    module_offering_id: UUID | None = None


class MessageRead(AuditFields):
    conversation_id: UUID
    author_user_id: UUID | None
    role: str
    sequence_number: int
    content_text: str
    content_blocks: list
    parent_message_id: UUID | None
    is_redacted: bool


class ConversationDetail(BaseModel):
    conversation: ConversationRead
    messages: list[MessageRead]


class ProviderAttemptRead(BaseModel):
    provider: str
    model: str
    status: str
    reason: str
    latency_ms: int | None = None
    error_code: str | None = None


class UnifiedAIResponse(BaseModel):
    conversation: ConversationRead
    user_message: MessageRead
    assistant_message: MessageRead
    classification: TaskClassification
    output: InlineOutput
    sources: list[SourceCard]
    integrity_warnings: list[str] = Field(default_factory=list)
    provider: str
    model: str
    provider_attempts: list[ProviderAttemptRead]
    generated_at: datetime


class ProviderStatusRead(BaseModel):
    provider: str
    configured: bool
    default_model: str
