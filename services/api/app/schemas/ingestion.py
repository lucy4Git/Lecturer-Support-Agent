from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from ..ingestion.contracts import IngestionOutcome
from .common import ORMModel


class ProcessDocumentRequest(BaseModel):
    force: bool = False


class ExtractedContentRead(ORMModel):
    id: UUID
    document_version_id: UUID
    extraction_status: str
    extraction_method: str
    detected_language: str | None
    page_count: int | None
    word_count: int
    table_count: int
    slide_count: int
    sheet_count: int
    transcript_required: bool
    quality_score: str | None
    extracted_at: datetime | None


class IngestionJobRead(ORMModel):
    id: UUID
    document_version_id: UUID
    status: str
    current_stage: str
    parser_name: str | None
    embedding_provider: str | None
    embedding_model: str | None
    attempt_count: int
    error_code: str | None
    error_message: str | None
    warnings: list
    metrics: dict
    started_at: datetime | None
    completed_at: datetime | None


class ProcessingStatusResponse(BaseModel):
    document_version_id: UUID
    extraction: ExtractedContentRead | None
    latest_job: IngestionJobRead | None
    chunk_count: int
    indexed: bool


class RetrievalPreviewRequest(BaseModel):
    query: str = Field(min_length=2, max_length=10_000)
    conversation_id: UUID | None = None
    attachment_version_ids: list[UUID] = Field(default_factory=list, max_length=20)


class RetrievalPreviewItem(BaseModel):
    source_key: str
    title: str
    locator: str | None
    excerpt: str
    relevance_score: float | None
    document_version_id: UUID


class RetrievalPreviewResponse(BaseModel):
    items: list[RetrievalPreviewItem]
    warnings: list[str] = Field(default_factory=list)


class ProcessDocumentResponse(BaseModel):
    outcome: IngestionOutcome
