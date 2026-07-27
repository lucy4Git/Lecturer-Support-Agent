from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from uuid import UUID, uuid4

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from services.database.models import (
    Document,
    DocumentChunk,
    DocumentVersion,
    ExtractedContent,
    IngestionJob,
    StorageObject,
)

from ..core.request_context import RequestContext
from ..core.settings import Settings, get_settings
from ..ingestion import DocumentParserRegistry, EmbeddingClient, IngestionOutcome, TextChunker
from ..integrations.object_storage import ObjectStorage
from ..integrations.qdrant import QdrantGateway
from .audit import AuditService
from .document_access import DocumentAccessService


class DocumentIngestionService:
    def __init__(
        self,
        session: AsyncSession,
        storage: ObjectStorage,
        context: RequestContext,
        *,
        settings: Settings | None = None,
        parser_registry: DocumentParserRegistry | None = None,
        chunker: TextChunker | None = None,
        embedding_client: EmbeddingClient,
        qdrant: QdrantGateway,
    ) -> None:
        self.session = session
        self.storage = storage
        self.context = context
        self.settings = settings or get_settings()
        self.parsers = parser_registry or DocumentParserRegistry()
        self.chunker = chunker or TextChunker(
            target_characters=self.settings.ingestion_chunk_characters,
            overlap_characters=self.settings.ingestion_chunk_overlap_characters,
        )
        self.embedding_client = embedding_client
        self.qdrant = qdrant
        self.audit = AuditService(session, context)

    async def process_version(self, version_id: UUID, *, force: bool = False) -> IngestionOutcome:
        accessible = await DocumentAccessService(self.session, self.context).require_version(version_id)
        document, version, storage_object = accessible.document, accessible.version, accessible.storage_object
        existing = await self.session.scalar(
            select(ExtractedContent).where(
                ExtractedContent.tenant_id == self.context.tenant_id,
                ExtractedContent.document_version_id == version.id,
            )
        )
        if existing is not None and version.indexed_at is not None and not force:
            count = len(
                list(
                    await self.session.scalars(
                        select(DocumentChunk.id).where(
                            DocumentChunk.tenant_id == self.context.tenant_id,
                            DocumentChunk.document_version_id == version.id,
                        )
                    )
                )
            )
            latest_job = await self.session.scalar(
                select(IngestionJob)
                .where(
                    IngestionJob.tenant_id == self.context.tenant_id,
                    IngestionJob.document_version_id == version.id,
                )
                .order_by(IngestionJob.created_at.desc())
                .limit(1)
            )
            if latest_job is None:
                latest_job = IngestionJob(
                    id=uuid4(),
                    tenant_id=self.context.tenant_id,
                    document_version_id=version.id,
                    requested_by_user_id=self.context.user_id,
                    requested_by_role_code=self.context.role_code,
                    status="completed",
                    current_stage="completed",
                    parser_name=existing.extraction_method,
                    embedding_provider=self.embedding_client.provider_name,
                    embedding_model=self.embedding_client.model_name,
                    attempt_count=0,
                    warnings=["Existing extraction and index were reused."],
                    metrics={"chunk_count": count, "indexed_chunk_count": count, "reused": True},
                    started_at=existing.extracted_at,
                    completed_at=version.indexed_at,
                )
                self.session.add(latest_job)
                await self.session.flush()
            return IngestionOutcome(
                job_id=latest_job.id,
                document_version_id=version.id,
                status="already_processed",
                extraction_status=existing.extraction_status,
                chunk_count=count,
                indexed_chunk_count=count,
                parser_name=existing.extraction_method,
                embedding_provider=self.embedding_client.provider_name,
                embedding_model=self.embedding_client.model_name,
            )

        job = IngestionJob(
            id=uuid4(),
            tenant_id=self.context.tenant_id,
            document_version_id=version.id,
            requested_by_user_id=self.context.user_id,
            requested_by_role_code=self.context.role_code,
            status="processing",
            current_stage="reading_object",
            attempt_count=1,
            embedding_provider=self.embedding_client.provider_name,
            embedding_model=self.embedding_client.model_name,
            started_at=datetime.now(timezone.utc),
        )
        self.session.add(job)
        await self.session.flush()
        try:
            content = await self.storage.get_bytes(
                object_key=storage_object.object_key,
                version_id=storage_object.storage_version_id,
            )
            job.current_stage = "extracting"
            extraction = self.parsers.extract(
                filename=version.original_filename,
                media_type=storage_object.media_type,
                content=content,
            )
            job.parser_name = extraction.parser_name
            job.warnings = extraction.warnings
            await self.session.execute(
                delete(DocumentChunk).where(
                    DocumentChunk.tenant_id == self.context.tenant_id,
                    DocumentChunk.document_version_id == version.id,
                )
            )
            if existing is None:
                existing = ExtractedContent(
                    id=uuid4(), tenant_id=self.context.tenant_id, document_version_id=version.id,
                    extraction_status=extraction.status, extraction_method=extraction.parser_name,
                )
                self.session.add(existing)
            existing.extraction_status = extraction.status
            existing.extraction_method = extraction.parser_name
            existing.text_content = extraction.text
            existing.text_sha256 = (
                hashlib.sha256(extraction.text.encode("utf-8")).hexdigest() if extraction.text else None
            )
            existing.detected_language = extraction.detected_language
            existing.page_count = extraction.page_count
            existing.word_count = extraction.word_count
            existing.table_count = extraction.table_count
            existing.slide_count = extraction.slide_count
            existing.sheet_count = extraction.sheet_count
            existing.transcript_required = extraction.transcript_required
            existing.quality_score = extraction.quality_score
            existing.extraction_metadata = extraction.metadata
            existing.extracted_at = datetime.now(timezone.utc)
            version.extracted_text_status = extraction.status

            if extraction.status != "extracted" or not extraction.text:
                version.indexed_at = None
                job.status = "completed_with_warnings"
                job.current_stage = "completed"
                job.completed_at = datetime.now(timezone.utc)
                job.metrics = {"chunk_count": 0, "indexed_chunk_count": 0}
                await self.audit.record(
                    action="document.ingestion_completed_without_index",
                    resource_type="document_version",
                    resource_id=version.id,
                    metadata={"status": extraction.status, "warnings": extraction.warnings},
                )
                await self.session.flush()
                return IngestionOutcome(
                    job_id=job.id,
                    document_version_id=version.id,
                    status=job.status,
                    extraction_status=extraction.status,
                    parser_name=extraction.parser_name,
                    warnings=extraction.warnings,
                )

            job.current_stage = "chunking"
            drafts = self.chunker.chunk(extraction.text)
            job.current_stage = "embedding"
            vectors = await self.embedding_client.embed([draft.text for draft in drafts])
            if len(vectors) != len(drafts):
                raise ValueError("Embedding count did not match document chunk count.")
            chunks: list[DocumentChunk] = []
            points: list[dict] = []
            now = datetime.now(timezone.utc)
            for draft, vector in zip(drafts, vectors, strict=True):
                point_id = str(uuid4())
                chunk = DocumentChunk(
                    id=uuid4(),
                    tenant_id=self.context.tenant_id,
                    document_version_id=version.id,
                    chunk_index=draft.index,
                    chunk_text=draft.text,
                    chunk_sha256=draft.sha256,
                    token_estimate=draft.token_estimate,
                    character_start=draft.character_start,
                    character_end=draft.character_end,
                    section_title=draft.section_title,
                    vector_point_id=point_id,
                    embedding_provider=self.embedding_client.provider_name,
                    embedding_model=self.embedding_client.model_name,
                    indexed_at=now,
                    chunk_metadata={"parser": extraction.parser_name},
                )
                self.session.add(chunk)
                chunks.append(chunk)
                points.append(
                    {
                        "id": point_id,
                        "vector": {"default": vector},
                        "payload": {
                            "tenant_id": str(self.context.tenant_id),
                            "document_id": str(document.id),
                            "document_version_id": str(version.id),
                            "document_chunk_id": str(chunk.id),
                            "chunk_index": draft.index,
                            "chunk_text": draft.text,
                            "chunk_sha256": draft.sha256,
                            "title": document.title,
                            "original_filename": version.original_filename,
                            "version_number": version.version_number,
                            "owner_user_id": str(document.owner_user_id),
                            "visibility": document.visibility,
                            "is_current": document.current_version_id == version.id,
                            "is_deleted": document.is_deleted,
                            "org_unit_id": str(document.org_unit_id) if document.org_unit_id else None,
                            "programme_id": str(document.programme_id) if document.programme_id else None,
                            "module_id": str(document.module_id) if document.module_id else None,
                            "document_type": document.document_type,
                            "source_type": "institutional_document",
                            "section_title": draft.section_title,
                        },
                    }
                )
            await self.session.flush()
            job.current_stage = "indexing"
            await self.qdrant.ensure_collection(vector_size=self.embedding_client.dimension)
            await self.qdrant.delete_document_version(
                tenant_id=self.context.tenant_id, document_version_id=version.id
            )
            await self.qdrant.upsert_points(points)
            version.indexed_at = now
            job.status = "completed"
            job.current_stage = "completed"
            job.completed_at = datetime.now(timezone.utc)
            job.metrics = {
                "bytes_read": len(content),
                "word_count": extraction.word_count,
                "chunk_count": len(chunks),
                "indexed_chunk_count": len(points),
            }
            await self.audit.record(
                action="document.ingestion_completed",
                resource_type="document_version",
                resource_id=version.id,
                metadata={"chunk_count": len(chunks), "parser": extraction.parser_name},
            )
            await self.session.flush()
            return IngestionOutcome(
                job_id=job.id,
                document_version_id=version.id,
                status=job.status,
                extraction_status=extraction.status,
                chunk_count=len(chunks),
                indexed_chunk_count=len(points),
                parser_name=extraction.parser_name,
                embedding_provider=self.embedding_client.provider_name,
                embedding_model=self.embedding_client.model_name,
                warnings=extraction.warnings,
            )
        except Exception as exc:
            job.status = "failed"
            job.current_stage = "failed"
            job.error_code = type(exc).__name__
            job.error_message = str(exc)[:4000]
            job.completed_at = datetime.now(timezone.utc)
            await self.audit.record(
                action="document.ingestion_failed",
                resource_type="document_version",
                resource_id=version.id,
                metadata={"safe_error_type": type(exc).__name__},
            )
            await self.session.flush()
            raise
