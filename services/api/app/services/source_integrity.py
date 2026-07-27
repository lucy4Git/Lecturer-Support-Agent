from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from services.database.models import (
    Citation,
    GeneratedOutput,
    OutputVersion,
    Source,
    SourceRetrieval,
    VerificationResult,
)

from ..core.request_context import RequestContext
from .audit import AuditService


def canonical_source_identifier(
    *, doi: str | None, url: str | None, title: str, stable_key: str | None = None
) -> str:
    if stable_key:
        return f"stable:{stable_key.strip().lower()}"
    if doi:
        return f"doi:{doi.strip().lower()}"
    if url:
        return f"url:{url.strip()}"
    digest = hashlib.sha256(title.strip().lower().encode("utf-8")).hexdigest()
    return f"title-sha256:{digest}"


class SourceIntegrityService:
    """Persist only sources that were genuinely retrieved for an AI request."""

    def __init__(self, session: AsyncSession, context: RequestContext) -> None:
        self.session = session
        self.context = context
        self.audit = AuditService(session, context)

    async def record_retrieval(
        self,
        *,
        ai_request_id: UUID,
        source_type: str,
        title: str,
        authors: list,
        publisher_or_organisation: str | None,
        publication_date: str | None,
        canonical_url: str | None,
        doi: str | None,
        licence: str | None,
        reliability_tier: str,
        is_institutional: bool,
        is_restricted: bool,
        retrieved_by: str,
        retrieval_query: str,
        rank: int | None = None,
        relevance_score: str | None = None,
        access_snapshot: dict | None = None,
        stable_key: str | None = None,
    ) -> SourceRetrieval:
        identifier = canonical_source_identifier(
            doi=doi, url=canonical_url, title=title, stable_key=stable_key
        )
        source = await self.session.scalar(
            select(Source).where(
                Source.tenant_id == self.context.tenant_id,
                Source.canonical_identifier == identifier,
            )
        )
        if source is None:
            source = Source(
                id=uuid4(),
                tenant_id=self.context.tenant_id,
                source_type=source_type,
                title=title,
                authors=authors,
                publisher_or_organisation=publisher_or_organisation,
                publication_date=publication_date,
                canonical_url=canonical_url,
                canonical_identifier=identifier,
                doi=doi,
                licence=licence,
                reliability_tier=reliability_tier,
                is_institutional=is_institutional,
                is_restricted=is_restricted,
                metadata_payload={"recorded_from_actual_retrieval": True},
            )
            self.session.add(source)
            await self.session.flush()

        retrieval = SourceRetrieval(
            id=uuid4(),
            tenant_id=self.context.tenant_id,
            ai_request_id=ai_request_id,
            source_id=source.id,
            retrieved_by=retrieved_by,
            retrieval_query=retrieval_query,
            retrieved_at=datetime.now(timezone.utc),
            rank=rank,
            relevance_score=relevance_score,
            access_snapshot=access_snapshot or {},
        )
        self.session.add(retrieval)
        await self.session.flush()
        await self.audit.record(
            action="source.retrieval_recorded",
            resource_type="source_retrieval",
            resource_id=retrieval.id,
            metadata={"source_id": str(source.id), "ai_request_id": str(ai_request_id)},
        )
        return retrieval

    async def create_citation(
        self,
        *,
        output_version_id: UUID,
        source_retrieval_id: UUID,
        citation_number: int,
        display_label: str,
        locator: str | None = None,
        supporting_excerpt: str | None = None,
    ) -> Citation:
        # A citation may only connect an output to a retrieval from the same AI
        # request. This prevents a model from naming an unobserved source.
        pair = await self.session.execute(
            select(OutputVersion, SourceRetrieval)
            .join(GeneratedOutput, GeneratedOutput.id == OutputVersion.generated_output_id)
            .join(
                SourceRetrieval,
                SourceRetrieval.ai_request_id == GeneratedOutput.ai_request_id,
            )
            .where(
                OutputVersion.tenant_id == self.context.tenant_id,
                OutputVersion.id == output_version_id,
                SourceRetrieval.tenant_id == self.context.tenant_id,
                SourceRetrieval.id == source_retrieval_id,
            )
        )
        if pair.first() is None:
            raise ValueError("Citation source was not retrieved for the output's AI request.")

        citation = Citation(
            id=uuid4(),
            tenant_id=self.context.tenant_id,
            output_version_id=output_version_id,
            source_retrieval_id=source_retrieval_id,
            citation_number=citation_number,
            locator=locator,
            supporting_excerpt_hash=(
                hashlib.sha256(supporting_excerpt.encode("utf-8")).hexdigest()
                if supporting_excerpt
                else None
            ),
            display_label=display_label,
            verified=False,
        )
        self.session.add(citation)
        await self.session.flush()
        return citation

    async def record_verification(
        self,
        *,
        citation_id: UUID,
        status: str,
        verifier: str,
        findings: dict,
    ) -> VerificationResult:
        citation = await self.session.scalar(
            select(Citation).where(
                Citation.tenant_id == self.context.tenant_id,
                Citation.id == citation_id,
            )
        )
        if citation is None:
            raise ValueError("Citation not found in the current tenant.")
        result = VerificationResult(
            id=uuid4(),
            tenant_id=self.context.tenant_id,
            target_type="citation",
            target_id=citation_id,
            verification_type="source_and_claim_integrity",
            status=status,
            verifier=verifier,
            findings=findings,
            verified_at=datetime.now(timezone.utc),
        )
        citation.verified = status == "verified"
        self.session.add(result)
        await self.session.flush()
        await self.audit.record(
            action="citation.verification_recorded",
            resource_type="citation",
            resource_id=citation_id,
            after_state={"status": status, "verified": citation.verified},
        )
        return result
