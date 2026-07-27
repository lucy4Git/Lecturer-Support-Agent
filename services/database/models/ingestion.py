from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, TenantOwnedMixin, TimestampMixin, UUIDPrimaryKeyMixin


class IngestionJob(Base, UUIDPrimaryKeyMixin, TenantOwnedMixin, TimestampMixin):
    __tablename__ = "ingestion_jobs"
    __table_args__ = (
        Index("ix_ingestion_job_version", "tenant_id", "document_version_id", "status"),
        {"schema": "ingestion"},
    )

    document_version_id: Mapped[UUID] = mapped_column(
        ForeignKey("content.document_versions.id"), nullable=False
    )
    upload_item_id: Mapped[UUID | None] = mapped_column(ForeignKey("ingestion.upload_items.id"))
    requested_by_user_id: Mapped[UUID] = mapped_column(ForeignKey("iam.users.id"), nullable=False)
    requested_by_role_code: Mapped[str] = mapped_column(String(80), nullable=False)
    status: Mapped[str] = mapped_column(String(40), default="queued", nullable=False)
    current_stage: Mapped[str] = mapped_column(String(60), default="queued", nullable=False)
    parser_name: Mapped[str | None] = mapped_column(String(120))
    embedding_provider: Mapped[str | None] = mapped_column(String(80))
    embedding_model: Mapped[str | None] = mapped_column(String(160))
    attempt_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    error_code: Mapped[str | None] = mapped_column(String(120))
    error_message: Mapped[str | None] = mapped_column(Text)
    warnings: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    metrics: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ExtractedContent(Base, UUIDPrimaryKeyMixin, TenantOwnedMixin, TimestampMixin):
    __tablename__ = "extracted_contents"
    __table_args__ = (
        UniqueConstraint("tenant_id", "document_version_id"),
        Index("ix_extracted_content_status", "tenant_id", "extraction_status"),
        {"schema": "content"},
    )

    document_version_id: Mapped[UUID] = mapped_column(
        ForeignKey("content.document_versions.id"), nullable=False
    )
    extraction_status: Mapped[str] = mapped_column(String(40), nullable=False)
    extraction_method: Mapped[str] = mapped_column(String(120), nullable=False)
    text_content: Mapped[str] = mapped_column(Text, default="", nullable=False)
    text_sha256: Mapped[str | None] = mapped_column(String(64))
    detected_language: Mapped[str | None] = mapped_column(String(30))
    page_count: Mapped[int | None] = mapped_column(Integer)
    word_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    table_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    slide_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    sheet_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    transcript_required: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    quality_score: Mapped[str | None] = mapped_column(String(30))
    extraction_metadata: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    extracted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class DocumentChunk(Base, UUIDPrimaryKeyMixin, TenantOwnedMixin, TimestampMixin):
    __tablename__ = "document_chunks"
    __table_args__ = (
        UniqueConstraint("tenant_id", "document_version_id", "chunk_index"),
        Index("ix_document_chunk_version", "tenant_id", "document_version_id", "chunk_index"),
        Index("ix_document_chunk_vector", "tenant_id", "vector_point_id"),
        {"schema": "content"},
    )

    document_version_id: Mapped[UUID] = mapped_column(
        ForeignKey("content.document_versions.id"), nullable=False
    )
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    chunk_text: Mapped[str] = mapped_column(Text, nullable=False)
    chunk_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    token_estimate: Mapped[int] = mapped_column(Integer, nullable=False)
    character_start: Mapped[int] = mapped_column(Integer, nullable=False)
    character_end: Mapped[int] = mapped_column(Integer, nullable=False)
    page_start: Mapped[int | None] = mapped_column(Integer)
    page_end: Mapped[int | None] = mapped_column(Integer)
    section_title: Mapped[str | None] = mapped_column(String(500))
    vector_point_id: Mapped[str | None] = mapped_column(String(80))
    embedding_provider: Mapped[str | None] = mapped_column(String(80))
    embedding_model: Mapped[str | None] = mapped_column(String(160))
    indexed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    chunk_metadata: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)


class DocumentVersionTransition(Base, UUIDPrimaryKeyMixin, TenantOwnedMixin, TimestampMixin):
    __tablename__ = "document_version_transitions"
    __table_args__ = (
        Index("ix_version_transition", "tenant_id", "document_version_id", "created_at"),
        {"schema": "content"},
    )

    document_version_id: Mapped[UUID] = mapped_column(
        ForeignKey("content.document_versions.id"), nullable=False
    )
    from_status: Mapped[str | None] = mapped_column(String(40))
    to_status: Mapped[str] = mapped_column(String(40), nullable=False)
    changed_by_user_id: Mapped[UUID] = mapped_column(ForeignKey("iam.users.id"), nullable=False)
    changed_by_role_code: Mapped[str] = mapped_column(String(80), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    transition_metadata: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)


class InstitutionalRetrievalTrace(Base, UUIDPrimaryKeyMixin, TenantOwnedMixin, TimestampMixin):
    __tablename__ = "institutional_retrieval_traces"
    __table_args__ = (
        Index("ix_institutional_retrieval_request", "tenant_id", "ai_request_id", "rank"),
        {"schema": "source"},
    )

    ai_request_id: Mapped[UUID] = mapped_column(ForeignKey("ai.ai_requests.id"), nullable=False)
    document_id: Mapped[UUID] = mapped_column(ForeignKey("content.documents.id"), nullable=False)
    document_version_id: Mapped[UUID] = mapped_column(
        ForeignKey("content.document_versions.id"), nullable=False
    )
    document_chunk_id: Mapped[UUID | None] = mapped_column(ForeignKey("content.document_chunks.id"))
    retrieval_query_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    rank: Mapped[int] = mapped_column(Integer, nullable=False)
    relevance_score: Mapped[str | None] = mapped_column(String(50))
    retrieval_method: Mapped[str] = mapped_column(String(80), nullable=False)
    used_in_prompt: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    permission_snapshot: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    locator: Mapped[str | None] = mapped_column(String(255))
