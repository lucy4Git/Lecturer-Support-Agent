from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from services.database.models import (
    Conversation,
    Document,
    DocumentChunk,
    DocumentVersion,
    ExtractedContent,
    InstitutionalRetrievalTrace,
)

from ..ai.contracts import SourceCandidate, TaskClassification
from ..core.request_context import RequestContext
from ..core.settings import Settings, get_settings
from ..ingestion.embeddings import EmbeddingClient
from ..integrations.qdrant import QdrantGateway, RetrievalScope
from .document_access import DocumentAccessService


@dataclass(slots=True)
class RetrievalBundle:
    sources: list[SourceCandidate] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


class DocumentRetrievalService:
    def __init__(
        self,
        session: AsyncSession,
        context: RequestContext,
        *,
        embedding_client: EmbeddingClient,
        qdrant: QdrantGateway,
        settings: Settings | None = None,
    ) -> None:
        self.session = session
        self.context = context
        self.embedding_client = embedding_client
        self.qdrant = qdrant
        self.settings = settings or get_settings()
        self.access = DocumentAccessService(session, context)

    async def retrieve(
        self,
        *,
        query: str,
        conversation: Conversation,
        attachment_version_ids: list[UUID],
        classification: TaskClassification,
        ai_request_id: UUID,
    ) -> RetrievalBundle:
        bundle = RetrievalBundle()
        seen: set[tuple[UUID, int | None]] = set()
        rank = 1
        for version_id in attachment_version_ids:
            accessible = await self.access.require_version(version_id)
            extraction = await self.session.scalar(
                select(ExtractedContent).where(
                    ExtractedContent.tenant_id == self.context.tenant_id,
                    ExtractedContent.document_version_id == version_id,
                )
            )
            if extraction is None or not extraction.text_content:
                bundle.warnings.append(
                    f"{accessible.version.original_filename} is attached but has not produced extractable text yet."
                )
                continue
            excerpt = extraction.text_content[: self.settings.retrieval_max_excerpt_characters]
            key = (version_id, None)
            if key in seen:
                continue
            seen.add(key)
            bundle.sources.append(
                self._candidate(
                    document=accessible.document,
                    version=accessible.version,
                    excerpt=excerpt,
                    rank=rank,
                    query=query,
                    locator="attached document",
                    chunk_id=None,
                )
            )
            await self._trace(
                ai_request_id=ai_request_id,
                document=accessible.document,
                version=accessible.version,
                chunk_id=None,
                query=query,
                rank=rank,
                score=None,
                method="direct_attachment",
                locator="attached document",
            )
            rank += 1

        should_search = bool(
            classification.institutional_context_required
            or attachment_version_ids
            or conversation.module_id
            or conversation.programme_id
            or conversation.org_unit_id
        )
        if not should_search or len(bundle.sources) >= self.settings.retrieval_max_chunks:
            return bundle
        try:
            query_vector = (await self.embedding_client.embed([query]))[0]
            scope = RetrievalScope(
                tenant_id=self.context.tenant_id,
                user_id=self.context.user_id,
                allowed_org_unit_ids=((conversation.org_unit_id,) if conversation.org_unit_id else ()),
                allowed_programme_ids=((conversation.programme_id,) if conversation.programme_id else ()),
                allowed_module_ids=((conversation.module_id,) if conversation.module_id else ()),
                include_public=False,
            )
            hits = await self.qdrant.search(
                vector=query_vector,
                scope=scope,
                limit=self.settings.retrieval_max_chunks * 2,
                score_threshold=self.settings.retrieval_min_score,
            )
        except Exception as exc:
            bundle.warnings.append(
                f"Authorised institutional retrieval was unavailable ({type(exc).__name__}); no institutional claim was fabricated."
            )
            return bundle

        for hit in hits:
            payload = hit.get("payload") or {}
            try:
                version_id = UUID(str(payload["document_version_id"]))
                chunk_id = UUID(str(payload["document_chunk_id"]))
            except (KeyError, ValueError):
                continue
            if (version_id, int(payload.get("chunk_index", -1))) in seen:
                continue
            accessible = await self.access.get_for_retrieval(version_id)
            if accessible is None:
                continue
            chunk = await self.session.scalar(
                select(DocumentChunk).where(
                    DocumentChunk.tenant_id == self.context.tenant_id,
                    DocumentChunk.id == chunk_id,
                    DocumentChunk.document_version_id == version_id,
                )
            )
            if chunk is None:
                continue
            seen.add((version_id, chunk.chunk_index))
            locator = (
                f"section {chunk.section_title}" if chunk.section_title else f"chunk {chunk.chunk_index + 1}"
            )
            bundle.sources.append(
                self._candidate(
                    document=accessible.document,
                    version=accessible.version,
                    excerpt=chunk.chunk_text[: self.settings.retrieval_max_excerpt_characters],
                    rank=rank,
                    query=query,
                    locator=locator,
                    chunk_id=chunk.id,
                    relevance_score=float(hit.get("score")) if hit.get("score") is not None else None,
                )
            )
            await self._trace(
                ai_request_id=ai_request_id,
                document=accessible.document,
                version=accessible.version,
                chunk_id=chunk.id,
                query=query,
                rank=rank,
                score=hit.get("score"),
                method="qdrant_semantic",
                locator=locator,
            )
            rank += 1
            if len(bundle.sources) >= self.settings.retrieval_max_chunks:
                break
        return bundle

    def _candidate(
        self,
        *,
        document: Document,
        version: DocumentVersion,
        excerpt: str,
        rank: int,
        query: str,
        locator: str,
        chunk_id: UUID | None,
        relevance_score: float | None = None,
    ) -> SourceCandidate:
        return SourceCandidate(
            source_key=f"institutional-{version.id}-{chunk_id or 'full'}",
            source_type="institutional_document",
            title=f"{document.title} (version {version.version_number})",
            authors=[],
            publisher_or_organisation="Authorised institutional material",
            publication_date=version.created_at.date().isoformat() if version.created_at else None,
            reliability_tier="institutional_versioned_source",
            retrieved_by="authorised_institutional_retrieval_v1",
            retrieval_query=query,
            rank=rank,
            relevance_score=relevance_score,
            metadata={
                "is_institutional": True,
                "is_restricted": document.visibility != "public",
                "document_id": str(document.id),
                "document_version_id": str(version.id),
                "document_chunk_id": str(chunk_id) if chunk_id else None,
                "version_number": version.version_number,
                "visibility": document.visibility,
                "locator": locator,
                "excerpt": excerpt,
                "original_filename": version.original_filename,
            },
        )

    async def _trace(
        self,
        *,
        ai_request_id: UUID,
        document: Document,
        version: DocumentVersion,
        chunk_id: UUID | None,
        query: str,
        rank: int,
        score: object,
        method: str,
        locator: str,
    ) -> None:
        self.session.add(
            InstitutionalRetrievalTrace(
                id=uuid4(),
                tenant_id=self.context.tenant_id,
                ai_request_id=ai_request_id,
                document_id=document.id,
                document_version_id=version.id,
                document_chunk_id=chunk_id,
                retrieval_query_sha256=hashlib.sha256(query.encode("utf-8")).hexdigest(),
                rank=rank,
                relevance_score=str(score) if score is not None else None,
                retrieval_method=method,
                used_in_prompt=True,
                permission_snapshot={
                    "user_id": str(self.context.user_id),
                    "active_role": self.context.role_code,
                    "role_assignment_id": str(self.context.role_assignment_id) if self.context.role_assignment_id else None,
                    "visibility": document.visibility,
                },
                locator=locator,
            )
        )
