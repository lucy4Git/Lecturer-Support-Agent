from __future__ import annotations

from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field


class ExtractionResult(BaseModel):
    status: Literal["extracted", "empty", "unsupported", "transcript_required", "failed"]
    parser_name: str
    text: str = ""
    page_count: int | None = None
    word_count: int = 0
    table_count: int = 0
    slide_count: int = 0
    sheet_count: int = 0
    detected_language: str | None = None
    transcript_required: bool = False
    quality_score: str | None = None
    warnings: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class IngestionOutcome(BaseModel):
    job_id: UUID
    document_version_id: UUID
    status: str
    extraction_status: str
    chunk_count: int = 0
    indexed_chunk_count: int = 0
    parser_name: str | None = None
    embedding_provider: str | None = None
    embedding_model: str | None = None
    warnings: list[str] = Field(default_factory=list)
