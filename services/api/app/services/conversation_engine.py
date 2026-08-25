from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import re
import time
from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import UUID, uuid4

from fastapi import HTTPException, Request, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from services.database.models import (
    AIRequest,
    AssessmentSafetyReview,
    Citation,
    Conversation,
    GeneratedOutput,
    Message,
    MessageAttachment,
    ModelExecution,
    OutputLifecycle,
    OutputVersion,
    OutputWorkflowAction,
    Source,
    SourceRetrieval,
)

from ..ai.contracts import (
    ChatMessage,
    ChatRole,
    InlineOutput,
    ProviderRequest,
    SourceCandidate,
    SourceCard,
    TaskClassification,
)
from ..ai.integrity import CitationIntegrityGuard, ClaimCitationVerifier
from ..ai.prompt_builder import PromptBuilder
from ..ai.router import ModelRouter, RoutedResponse
from ..ai.source_discovery import CompositeSourceDiscovery, CrossrefSourceDiscovery, OpenAlexSourceDiscovery
from ..ai.task_classifier import TeachingTaskClassifier
from ..ai.capability_registry import CapabilityRegistry
from ..core.request_context import RequestContext
from ..core.settings import Settings
from ..schemas.conversations import ConversationCreate, MessageCreate
from .audit import AuditService
from .authorization import AuthorizationService
from .source_integrity import SourceIntegrityService
from .assessment_safety import AssessmentSafetyEvaluator
from .commercial_analytics import AIUsageGovernanceService
from .document_retrieval import DocumentRetrievalService
from .module_context import ModuleContextBundle, ModuleContextService
from .teaching_output_workflow import TeachingOutputWorkflow


_stream_logger = logging.getLogger("lsa.engine.stream")

# Starlette's StreamingResponse only ever notices a client disconnect when its
# own send() call fails — it never proactively watches the connection. That
# is fine while the generator is actively yielding, but a provider's
# `anext()` can sit blocked waiting on a stalled network read indefinitely,
# and no send() attempt happens while blocked, so nothing ever tells the
# generator to stop. Polling `request.is_disconnected()` on a background
# task, and racing it against the provider's next-token future, closes that
# gap. 0.25s keeps detection prompt without busy-looping.
_DISCONNECT_POLL_INTERVAL_SECONDS = 0.25


class _ClientDisconnected(BaseException):
    """Raised when our own disconnect watcher detects the client is gone,
    independent of Starlette's own send()-failure detection.

    Deliberately a BaseException, not an Exception — exactly like the
    built-in GeneratorExit it stands in for — so it can never be
    misclassified by an `except Exception` handler as a genuine provider or
    persistence failure. Callers that need cleanup around it must catch it
    explicitly and either handle it or re-raise."""


def _log_stream_phase(
    phase: str,
    *,
    request_id: str | None = None,
    conversation_id: UUID | str | None = None,
    tenant_id: UUID | str | None = None,
    provider: str | None = None,
    model: str | None = None,
    elapsed_ms: float | None = None,
    outcome: str | None = None,
) -> None:
    """Structured, PII-safe phase logging for the streaming lifecycle.

    Never pass prompt text, assistant text, credentials, cookies, tokens, or
    any other request/response payload here — only identifiers and timing."""
    _stream_logger.info(
        phase,
        extra={
            "phase": phase,
            "request_id": request_id,
            "conversation_id": str(conversation_id) if conversation_id else None,
            "tenant_id": str(tenant_id) if tenant_id else None,
            "provider": provider,
            "model": model,
            "elapsed_ms": elapsed_ms,
            "outcome": outcome,
        },
    )


async def _watch_for_disconnect(request: Request, event: asyncio.Event) -> None:
    try:
        while not event.is_set():
            if await request.is_disconnected():
                event.set()
                return
            await asyncio.sleep(_DISCONNECT_POLL_INTERVAL_SECONDS)
    except asyncio.CancelledError:
        raise


async def _consume_cancellable(
    agen: AsyncIterator[str],
    disconnect_event: asyncio.Event,
) -> AsyncIterator[str]:
    """Yield items from `agen`, but if `disconnect_event` fires while a
    provider `anext()` is in flight — including one that is blocked
    indefinitely waiting for the next network chunk — cancel that in-flight
    call, close the provider's async generator (running its `async with`
    cleanup via the same GeneratorExit-through-aclose() mechanism proven in
    tests/unit/test_stream_cancellation.py), and raise
    `_ClientDisconnected` instead of silently stopping."""
    iterator = agen.__aiter__()
    while True:
        next_task = asyncio.ensure_future(iterator.__anext__())
        disconnect_task = asyncio.ensure_future(disconnect_event.wait())
        try:
            await asyncio.wait({next_task, disconnect_task}, return_when=asyncio.FIRST_COMPLETED)
        finally:
            pass

        if disconnect_event.is_set():
            _log_stream_phase("generation.provider.cancel_requested")
            next_task.cancel()
            with contextlib.suppress(BaseException):
                await next_task
            with contextlib.suppress(BaseException):
                await agen.aclose()
            _log_stream_phase("generation.provider.closed")
            disconnect_task.cancel()
            with contextlib.suppress(BaseException):
                await disconnect_task
            raise _ClientDisconnected()

        disconnect_task.cancel()
        with contextlib.suppress(BaseException):
            await disconnect_task
        try:
            item = next_task.result()
        except StopAsyncIteration:
            return
        yield item


class ConversationEngine:
    def __init__(
        self,
        session: AsyncSession,
        context: RequestContext,
        settings: Settings,
        *,
        classifier: TeachingTaskClassifier | None = None,
        router: ModelRouter | None = None,
        source_discovery: object | None = None,
        integrity_guard: CitationIntegrityGuard | None = None,
        prompt_builder: PromptBuilder | None = None,
        document_retrieval: DocumentRetrievalService | None = None,
    ) -> None:
        self.session = session
        self.context = context
        self.settings = settings
        self.classifier = classifier or TeachingTaskClassifier()
        self.router = router or ModelRouter(settings)
        self.source_discovery = source_discovery or CompositeSourceDiscovery([CrossrefSourceDiscovery(settings), OpenAlexSourceDiscovery(settings)])
        self.integrity_guard = integrity_guard or CitationIntegrityGuard()
        self.claim_verifier = ClaimCitationVerifier()
        self.prompt_builder = prompt_builder or PromptBuilder()
        self.document_retrieval = document_retrieval
        self.audit = AuditService(session, context)
        self.safety = AssessmentSafetyEvaluator()
        self.output_workflow = TeachingOutputWorkflow()
        self.module_context = ModuleContextService(session, context)

    async def create_conversation(self, payload: ConversationCreate) -> Conversation:
        await self._require_ai_permission()
        title = payload.title.strip() if payload.title else "New teaching conversation"
        conversation = Conversation(
            id=uuid4(),
            tenant_id=self.context.tenant_id,
            owner_user_id=self.context.user_id,
            title=title,
            org_unit_id=payload.org_unit_id,
            programme_id=payload.programme_id,
            module_id=payload.module_id,
            context=payload.context,
        )
        self.session.add(conversation)
        await self.session.flush()
        await self.audit.record(
            action="conversation.created",
            resource_type="conversation",
            resource_id=conversation.id,
            after_state={"title": title},
        )
        return conversation

    async def list_conversations(self, *, limit: int = 50, archived: bool | None = False) -> list[Conversation]:
        await self._require_ai_permission()
        conditions = [
            Conversation.tenant_id == self.context.tenant_id,
            Conversation.owner_user_id == self.context.user_id,
            # Deleted conversations are tombstoned via context.deleted_at (see
            # soft_delete_conversation) rather than a schema column, so they
            # never appear in Active or Archived — distinct from is_archived.
            Conversation.context["deleted_at"].astext.is_(None),
        ]
        if archived is not None:
            conditions.append(Conversation.is_archived.is_(archived))
        rows = await self.session.scalars(
            select(Conversation)
            .where(*conditions)
            .order_by(Conversation.updated_at.desc())
            .limit(limit)
        )
        return list(rows)

    async def get_conversation(self, conversation_id: UUID) -> tuple[Conversation, list[Message]]:
        await self._require_ai_permission()
        conversation = await self._owned_conversation(conversation_id)
        messages = list(
            await self.session.scalars(
                select(Message)
                .where(
                    Message.tenant_id == self.context.tenant_id,
                    Message.conversation_id == conversation_id,
                )
                .order_by(Message.sequence_number)
            )
        )
        return conversation, messages

    async def update_conversation(self, conversation_id: UUID, payload: "ConversationUpdate") -> Conversation:
        from ..schemas.conversations import ConversationUpdate  # noqa: PLC0415
        conversation = await self._owned_conversation(conversation_id)
        if payload.title is not None:
            conversation.title = payload.title.strip() or conversation.title
        if payload.is_archived is not None and payload.is_archived != conversation.is_archived:
            conversation.is_archived = payload.is_archived
            await self.audit.record(
                action="conversation.archived" if payload.is_archived else "conversation.unarchived",
                resource_type="conversation",
                resource_id=conversation.id,
            )
        await self.session.flush()
        await self.session.refresh(conversation)
        return conversation

    async def soft_delete_conversation(self, conversation_id: UUID) -> Conversation:
        """Delete is distinct from Archive: a deleted conversation is tombstoned
        via context.deleted_at and never appears in Active or Archived lists,
        and cannot be reopened or unarchived. Retention/audit conventions in
        this codebase favour soft deletion over destroying rows outright, so
        the underlying row and its messages are preserved for compliance —
        the product-facing "Delete" action is honestly a durable removal from
        the user's ordinary conversation history, not a promise of physical
        erasure, matching how audited data is handled elsewhere in this app.
        """
        conversation = await self._owned_conversation(conversation_id)
        conversation.context = {
            **conversation.context,
            "deleted_at": datetime.now(timezone.utc).isoformat(),
        }
        await self.audit.record(
            action="conversation.deleted",
            resource_type="conversation",
            resource_id=conversation.id,
        )
        await self.session.flush()
        await self.session.refresh(conversation)
        return conversation

    async def submit_message(
        self,
        *,
        conversation_id: UUID,
        payload: MessageCreate,
    ) -> tuple[
        Conversation,
        Message,
        Message,
        TaskClassification,
        InlineOutput,
        list[SourceCard],
        RoutedResponse,
        list[str],
    ]:
        await self._require_ai_permission()
        conversation = await self._owned_conversation(conversation_id)
        classification = self.classifier.classify(
            payload.content,
            has_attachments=bool(payload.attachment_version_ids),
        )
        usage_governance = AIUsageGovernanceService(self.session, self.context)
        usage_decision = await usage_governance.preflight(classification)
        if usage_decision.source_required and not classification.source_verification_required:
            classification = classification.model_copy(update={"source_verification_required": True})
        self.safety.enforce_generation_role(classification.task_type, self.context.role_code)
        ai_selection = self._resolve_ai_selection(conversation, payload, usage_decision)
        if ai_selection.persist is not None:
            conversation.context = {**conversation.context, "ai_selection": ai_selection.persist}
        module_bundle: ModuleContextBundle | None = None
        selected_offering_id = payload.module_offering_id
        if selected_offering_id is None and conversation.context.get("module_offering_id"):
            try:
                selected_offering_id = UUID(str(conversation.context["module_offering_id"]))
            except (TypeError, ValueError):
                selected_offering_id = None
        if selected_offering_id is not None:
            module_bundle = await self.module_context.require(selected_offering_id)
            conversation.context = {
                **conversation.context,
                "module_offering_id": str(selected_offering_id),
                "module_id": str(module_bundle.module_id),
                "module_code": module_bundle.module_code,
                "module_name": module_bundle.module_name,
            }
        next_sequence = int(
            await self.session.scalar(
                select(func.coalesce(func.max(Message.sequence_number), 0)).where(
                    Message.tenant_id == self.context.tenant_id,
                    Message.conversation_id == conversation.id,
                )
            )
            or 0
        ) + 1
        user_message = Message(
            id=uuid4(),
            tenant_id=self.context.tenant_id,
            conversation_id=conversation.id,
            author_user_id=self.context.user_id,
            role="user",
            sequence_number=next_sequence,
            content_text=payload.content,
            content_blocks=[],
        )
        self.session.add(user_message)
        await self.session.flush()
        for version_id in payload.attachment_version_ids:
            self.session.add(
                MessageAttachment(
                    id=uuid4(),
                    tenant_id=self.context.tenant_id,
                    message_id=user_message.id,
                    document_version_id=version_id,
                    attachment_purpose="context",
                )
            )

        ai_request = AIRequest(
            id=uuid4(),
            tenant_id=self.context.tenant_id,
            conversation_id=conversation.id,
            message_id=user_message.id,
            requested_by_user_id=self.context.user_id,
            intent=classification.task_type.value,
            output_type=classification.task_type.value,
            privacy_classification=classification.privacy_classification.value,
            institutional_context_required=classification.institutional_context_required,
            source_verification_required=classification.source_verification_required,
            routing_constraints={
                "classifier_version": self.classifier.VERSION,
                "confidence": classification.confidence,
                "rationale_codes": classification.rationale_codes,
                "detected_entities": classification.detected_entities,
                "human_review_required": classification.human_review_required,
                "module_offering_id": str(selected_offering_id) if selected_offering_id else None,
                "module_context_version": "snapshot-1.0" if module_bundle else None,
                "ai_usage_governance": usage_decision.as_dict(),
            },
        )
        self.session.add(ai_request)
        await self.session.flush()
        if module_bundle is not None:
            await self.module_context.persist_snapshot(
                ai_request_id=ai_request.id,
                conversation_id=conversation.id,
                bundle=module_bundle,
            )

        retrieval_warnings: list[str] = []
        institutional_sources: list[SourceCandidate] = []
        if self.document_retrieval is not None:
            bundle = await self.document_retrieval.retrieve(
                query=payload.content,
                conversation=conversation,
                attachment_version_ids=payload.attachment_version_ids,
                classification=classification,
                ai_request_id=ai_request.id,
            )
            institutional_sources = bundle.sources
            retrieval_warnings = bundle.warnings
        external_sources = await self._discover_sources(payload.content, classification)
        sources = self._merge_sources(institutional_sources, external_sources)
        history = await self._history(conversation.id)
        capability_result = await CapabilityRegistry(self.session, self.context).resolve(payload.content)
        augmented_context = payload.institutional_context or ""
        if capability_result.matched and capability_result.institutional_context:
            augmented_context = (
                (augmented_context + "\n\n" if augmented_context else "")
                + capability_result.institutional_context
            )
        system_prompt = self.prompt_builder.build_system_prompt(
            classification=classification,
            user_role=self.context.role_code,
            sources=sources,
            institutional_context=augmented_context or None,
            module_context=(module_bundle.prompt_text() if module_bundle else None),
        )
        routed = await self.router.generate(
            ProviderRequest(
                messages=history,
                system_prompt=system_prompt,
                model=ai_selection.model_override or "",
                max_output_tokens=self.settings.ai_max_output_tokens,
                temperature=self.settings.ai_temperature,
                metadata={
                    "tenant_id": str(self.context.tenant_id),
                    "conversation_id": str(conversation.id),
                    "ai_request_id": str(ai_request.id),
                    "task_type": classification.task_type.value,
                    "module_offering_id": str(selected_offering_id) if selected_offering_id else None,
                },
            ),
            privacy=classification.privacy_classification,
            allowed_providers=ai_selection.allowed_providers,
            denied_providers=ai_selection.denied_providers,
        )
        combined_sources = self._merge_sources(sources, routed.response.provider_sources)
        integrity = self.integrity_guard.validate(routed.response.text, combined_sources)
        claim_verification = self.claim_verifier.verify(integrity.text, combined_sources)
        integrity_warnings = [*retrieval_warnings, *integrity.warnings]
        if claim_verification["unsupported_claim_count"]:
            integrity_warnings.append(
                f"{claim_verification['unsupported_claim_count']} factual or quantitative claim(s) lack a verified source marker and require review."
            )
        if classification.source_verification_required and not combined_sources:
            integrity_warnings.append(
                "No verified external sources were available for this response; no citations were fabricated."
            )
        model_execution_id = await self._record_model_attempts(ai_request.id, routed)
        await usage_governance.record_usage(
            provider=routed.response.provider,
            model_id=routed.response.model,
            task_type=classification.task_type.value,
            status_code="completed",
            input_tokens=routed.response.input_tokens,
            output_tokens=routed.response.output_tokens,
            latency_ms=routed.response.latency_ms,
            currency_code=usage_decision.currency_code,
        )
        integrity_warnings.extend(
            code.replace("_", " ").capitalize()
            for code in usage_decision.warning_codes
            if code not in integrity_warnings
        )
        title = self._title_from_output(integrity.text, payload.content)
        generated_output = GeneratedOutput(
            id=uuid4(),
            tenant_id=self.context.tenant_id,
            conversation_id=conversation.id,
            source_message_id=user_message.id,
            ai_request_id=ai_request.id,
            output_type=classification.task_type.value,
            title=title,
            is_formally_approved=False,
            approval_disclaimer=(
                "AI-generated draft requiring authorised human review before formal use."
                if classification.human_review_required
                else "AI-generated teaching support output; lecturer review is recommended."
            ),
        )
        self.session.add(generated_output)
        await self.session.flush()

        module_context_data = module_bundle.as_dict() if module_bundle else None
        structured_content = self.output_workflow.structure(
            task_type=classification.task_type,
            markdown=integrity.text,
            classification=classification.model_dump(mode="json"),
            module_context=module_context_data,
        )
        structured_content.update(
            {
                "integrity_warnings": integrity_warnings,
                "source_keys": integrity.cited_source_keys,
                "claim_citation_verification": claim_verification,
            }
        )
        safety_evaluation = self.safety.evaluate(
            task_type=classification.task_type,
            content=integrity.text,
            detected_total_marks=(
                int(classification.detected_entities["total_marks"])
                if classification.detected_entities.get("total_marks") is not None
                else None
            ),
            module_context_available=module_bundle is not None,
        )
        integrity_warnings.extend(
            warning for warning in safety_evaluation.warnings if warning not in integrity_warnings
        )
        integrity_warnings.extend(
            warning
            for warning in structured_content.get("quality_warnings", [])
            if warning not in integrity_warnings
        )
        output_version = OutputVersion(
            id=uuid4(),
            tenant_id=self.context.tenant_id,
            generated_output_id=generated_output.id,
            version_number=1,
            previous_version_id=None,
            created_by_user_id=self.context.user_id,
            model_execution_id=model_execution_id,
            content_text=integrity.text,
            structured_content=structured_content,
            change_reason="Initial AI-generated inline output",
        )
        self.session.add(output_version)
        await self.session.flush()
        generated_output.current_version_id = output_version.id

        lifecycle = OutputLifecycle(
            id=uuid4(),
            tenant_id=self.context.tenant_id,
            generated_output_id=generated_output.id,
            owner_user_id=self.context.user_id,
            module_id=(module_bundle.module_id if module_bundle else conversation.module_id),
            module_offering_id=(module_bundle.module_offering_id if module_bundle else None),
            workflow_status="draft",
            risk_level=safety_evaluation.risk_level.value,
            assessment_kind=(
                classification.task_type.value
                if safety_evaluation.risk_level.value != "none"
                else None
            ),
            review_required=(
                classification.human_review_required
                or safety_evaluation.risk_level.value != "none"
            ),
            answer_key_present=safety_evaluation.answers_detected,
            student_release_allowed=safety_evaluation.student_copy_safe,
            policy_snapshot={
                "assessment_safety_version": self.safety.VERSION,
                "workflow_version": self.output_workflow.VERSION,
                "privacy_classification": classification.privacy_classification.value,
            },
        )
        safety_review = AssessmentSafetyReview(
            id=uuid4(),
            tenant_id=self.context.tenant_id,
            generated_output_id=generated_output.id,
            output_version_id=output_version.id,
            status=safety_evaluation.status.value,
            risk_level=safety_evaluation.risk_level.value,
            checks=safety_evaluation.checks,
            warnings=safety_evaluation.warnings,
            blocked_reasons=safety_evaluation.blocked_reasons,
            answers_detected=safety_evaluation.answers_detected,
            personal_data_detected=safety_evaluation.personal_data_detected,
            student_copy_safe=safety_evaluation.student_copy_safe,
        )
        workflow_action = OutputWorkflowAction(
            id=uuid4(),
            tenant_id=self.context.tenant_id,
            generated_output_id=generated_output.id,
            output_version_id=output_version.id,
            action="created",
            previous_status=None,
            new_status="draft",
            performed_by_user_id=self.context.user_id,
            active_role_code=self.context.role_code,
            reason="Initial AI-generated output created in the unified conversation.",
            action_metadata={
                "provider": routed.response.provider,
                "model": routed.response.model,
                "safety_status": safety_evaluation.status.value,
            },
        )
        self.session.add_all([lifecycle, safety_review, workflow_action])
        await self.session.flush()

        assistant_message = Message(
            id=uuid4(),
            tenant_id=self.context.tenant_id,
            conversation_id=conversation.id,
            author_user_id=None,
            role="assistant",
            sequence_number=next_sequence + 1,
            content_text=integrity.text,
            content_blocks=[
                {
                    "type": "inline_output",
                    "output_type": classification.task_type.value,
                    "title": title,
                    "editable": True,
                    "generated_output_id": str(generated_output.id),
                    "output_version_id": str(output_version.id),
                    "version_number": 1,
                    "workflow_status": lifecycle.workflow_status,
                    "risk_level": lifecycle.risk_level,
                    "safety_status": safety_review.status,
                    "requires_human_review": lifecycle.review_required,
                    "approval_disclaimer": generated_output.approval_disclaimer,
                }
            ],
            parent_message_id=user_message.id,
        )
        self.session.add(assistant_message)
        await self.session.flush()

        source_cards = await self._persist_sources_and_citations(
            ai_request_id=ai_request.id,
            output_version_id=output_version.id,
            sources=combined_sources,
            cited_source_keys=set(integrity.cited_source_keys),
        )
        if conversation.title == "New teaching conversation":
            conversation.title = self._title_from_request(payload.content)
        await self.audit.record(
            action="ai.response_generated",
            resource_type="generated_output",
            resource_id=generated_output.id,
            metadata={
                "task_type": classification.task_type.value,
                "provider": routed.response.provider,
                "model": routed.response.model,
                "source_count": len(source_cards),
                "citation_integrity_warnings": integrity_warnings,
                "workflow_status": lifecycle.workflow_status,
                "safety_status": safety_review.status,
                "risk_level": lifecycle.risk_level,
                "module_offering_id": str(lifecycle.module_offering_id) if lifecycle.module_offering_id else None,
            },
        )
        await self.session.flush()
        await self.session.refresh(conversation)
        output = InlineOutput(
            output_type=classification.task_type,
            title=title,
            markdown=integrity.text,
            requires_human_review=lifecycle.review_required,
            approval_disclaimer=generated_output.approval_disclaimer,
            metadata={
                "generated_output_id": str(generated_output.id),
                "output_version_id": str(output_version.id),
                "provider": routed.response.provider,
                "model": routed.response.model,
                "version_number": 1,
                "workflow_status": lifecycle.workflow_status,
                "risk_level": lifecycle.risk_level,
                "safety_status": safety_review.status,
                "safety_warnings": safety_review.warnings,
                "module_context": module_context_data or {},
            },
        )
        return (
            conversation,
            user_message,
            assistant_message,
            classification,
            output,
            source_cards,
            routed,
            integrity_warnings,
        )

    async def stream_message(
        self,
        *,
        conversation_id: UUID,
        payload: MessageCreate,
        request: Request | None = None,
    ) -> AsyncIterator[str]:
        """Async generator that yields SSE-formatted lines for streaming responses.

        Protocol:
          data: {"type": "thinking", "status": "…"}\n\n
          data: {"type": "token", "text": "…"}\n\n
          data: {"type": "done", …full metadata…}\n\n
          data: {"type": "error", "detail": "…"}\n\n

        `request` is optional only so existing callers/tests that construct
        this generator directly keep working; the real route always passes
        it. Without it, a client disconnect while the provider is blocked
        waiting for its next token cannot be detected proactively — see
        `_consume_cancellable` / `_watch_for_disconnect`.
        """

        def _sse(payload: dict) -> str:
            return f"data: {json.dumps(payload)}\n\n"

        stream_started_at = time.monotonic()
        request_id = getattr(request.state, "request_id", None) if request is not None else None
        if request_id is None:
            request_id = self.context.request_id

        disconnect_event = asyncio.Event()
        watcher_task: asyncio.Task | None = None
        if request is not None:
            watcher_task = asyncio.ensure_future(_watch_for_disconnect(request, disconnect_event))

        _log_stream_phase(
            "generation.request.accepted",
            request_id=request_id,
            conversation_id=conversation_id,
            tenant_id=self.context.tenant_id,
        )

        try:
            await self._require_ai_permission()
            yield _sse({"type": "thinking", "status": "Analysing your request…"})

            conversation = await self._owned_conversation(conversation_id)
            classification = self.classifier.classify(
                payload.content,
                has_attachments=bool(payload.attachment_version_ids),
            )
            usage_governance = AIUsageGovernanceService(self.session, self.context)
            usage_decision = await usage_governance.preflight(classification)
            if usage_decision.source_required and not classification.source_verification_required:
                classification = classification.model_copy(update={"source_verification_required": True})
            self.safety.enforce_generation_role(classification.task_type, self.context.role_code)
            ai_selection = self._resolve_ai_selection(conversation, payload, usage_decision)
            if ai_selection.persist is not None:
                conversation.context = {**conversation.context, "ai_selection": ai_selection.persist}

            module_bundle: ModuleContextBundle | None = None
            selected_offering_id = payload.module_offering_id
            if selected_offering_id is None and conversation.context.get("module_offering_id"):
                try:
                    selected_offering_id = UUID(str(conversation.context["module_offering_id"]))
                except (TypeError, ValueError):
                    selected_offering_id = None
            if selected_offering_id is not None:
                module_bundle = await self.module_context.require(selected_offering_id)
                conversation.context = {
                    **conversation.context,
                    "module_offering_id": str(selected_offering_id),
                    "module_id": str(module_bundle.module_id),
                    "module_code": module_bundle.module_code,
                    "module_name": module_bundle.module_name,
                }

            next_sequence = int(
                await self.session.scalar(
                    select(func.coalesce(func.max(Message.sequence_number), 0)).where(
                        Message.tenant_id == self.context.tenant_id,
                        Message.conversation_id == conversation.id,
                    )
                )
                or 0
            ) + 1
            user_message = Message(
                id=uuid4(),
                tenant_id=self.context.tenant_id,
                conversation_id=conversation.id,
                author_user_id=self.context.user_id,
                role="user",
                sequence_number=next_sequence,
                content_text=payload.content,
                content_blocks=[],
            )
            self.session.add(user_message)
            await self.session.flush()
            for version_id in payload.attachment_version_ids:
                self.session.add(
                    MessageAttachment(
                        id=uuid4(),
                        tenant_id=self.context.tenant_id,
                        message_id=user_message.id,
                        document_version_id=version_id,
                        attachment_purpose="context",
                    )
                )

            ai_request = AIRequest(
                id=uuid4(),
                tenant_id=self.context.tenant_id,
                conversation_id=conversation.id,
                message_id=user_message.id,
                requested_by_user_id=self.context.user_id,
                intent=classification.task_type.value,
                output_type=classification.task_type.value,
                privacy_classification=classification.privacy_classification.value,
                institutional_context_required=classification.institutional_context_required,
                source_verification_required=classification.source_verification_required,
                routing_constraints={
                    "classifier_version": self.classifier.VERSION,
                    "confidence": classification.confidence,
                    "rationale_codes": classification.rationale_codes,
                    "detected_entities": classification.detected_entities,
                    "human_review_required": classification.human_review_required,
                    "module_offering_id": str(selected_offering_id) if selected_offering_id else None,
                },
            )
            self.session.add(ai_request)
            await self.session.flush()
            if module_bundle is not None:
                await self.module_context.persist_snapshot(
                    ai_request_id=ai_request.id,
                    conversation_id=conversation.id,
                    bundle=module_bundle,
                )

            yield _sse({"type": "thinking", "status": "Retrieving relevant knowledge…"})

            retrieval_warnings: list[str] = []
            institutional_sources: list[SourceCandidate] = []
            if self.document_retrieval is not None:
                bundle = await self.document_retrieval.retrieve(
                    query=payload.content,
                    conversation=conversation,
                    attachment_version_ids=payload.attachment_version_ids,
                    classification=classification,
                    ai_request_id=ai_request.id,
                )
                institutional_sources = bundle.sources
                retrieval_warnings = bundle.warnings
            external_sources = await self._discover_sources(payload.content, classification)
            sources = self._merge_sources(institutional_sources, external_sources)
            history = await self._history(conversation.id)
            capability_result = await CapabilityRegistry(self.session, self.context).resolve(payload.content)
            augmented_context = payload.institutional_context or ""
            if capability_result.matched and capability_result.institutional_context:
                augmented_context = (
                    (augmented_context + "\n\n" if augmented_context else "")
                    + capability_result.institutional_context
                )

            # Short-circuit for system-level access denials — do not call the AI.
            # Ollama cannot override a real DB permission check result.
            if capability_result.matched and "ACCESS DENIED" in (capability_result.institutional_context or ""):
                denial_lines = [
                    ln for ln in capability_result.institutional_context.splitlines()
                    if ln and not ln.startswith("REAL PERMISSION CHECK") and not ln.startswith("INSTRUCTION:")
                ]
                denial_text = "\n".join(denial_lines).strip() or capability_result.institutional_context
                yield _sse({"type": "thinking", "status": "Checking permissions…"})
                yield _sse({"type": "token", "text": denial_text})
                yield _sse({
                    "type": "done",
                    "conversation_id": str(conversation.id),
                    "conversation_title": conversation.title or "",
                    "user_message_id": str(user_message.id),
                    "assistant_message_id": "",
                    "output_type": "permission_denied",
                    "title": payload.content[:60],
                    "generated_output_id": "",
                    "output_version_id": "",
                    "version_number": 0,
                    "workflow_status": "denied",
                    "risk_level": "none",
                    "safety_status": "passed",
                    "requires_human_review": False,
                    "approval_disclaimer": "",
                    "integrity_warnings": [],
                    "pending_action_token": None,
                    "pending_action_label": "",
                    "pending_action_details": [],
                    "sources": [],
                })
                return

            system_prompt = self.prompt_builder.build_system_prompt(
                classification=classification,
                user_role=self.context.role_code,
                sources=sources,
                institutional_context=augmented_context or None,
                module_context=(module_bundle.prompt_text() if module_bundle else None),
            )

            yield _sse({"type": "thinking", "status": "Generating response…"})

            # Deterministic direct output from capability (bypasses AI)
            # Used for assessment generation and review lifecycle operations.
            stream_result: dict[str, str] = {}
            if capability_result.direct_output:
                full_text = capability_result.direct_output
                chunk_size = 120
                for i in range(0, len(full_text), chunk_size):
                    yield _sse({"type": "token", "text": full_text[i:i + chunk_size]})
            else:
                # Stream AI tokens. Consumption is routed through
                # _consume_cancellable so a client disconnect can interrupt a
                # provider `anext()` that is blocked waiting for the next
                # network chunk — not just one that is actively yielding.
                full_text = ""
                first_token_seen = False
                _log_stream_phase(
                    "generation.provider.start",
                    request_id=request_id,
                    conversation_id=conversation.id,
                    tenant_id=self.context.tenant_id,
                    elapsed_ms=(time.monotonic() - stream_started_at) * 1000,
                )
                provider_stream = self.router.stream(
                    ProviderRequest(
                        messages=history,
                        system_prompt=system_prompt,
                        model=ai_selection.model_override or "",
                        max_output_tokens=self.settings.ai_max_output_tokens,
                        temperature=self.settings.ai_temperature,
                        metadata={
                            "tenant_id": str(self.context.tenant_id),
                            "conversation_id": str(conversation.id),
                            "ai_request_id": str(ai_request.id),
                            "task_type": classification.task_type.value,
                        },
                    ),
                    privacy=classification.privacy_classification,
                    allowed_providers=ai_selection.allowed_providers,
                    denied_providers=ai_selection.denied_providers,
                    result_holder=stream_result,
                )
                try:
                    async for token in _consume_cancellable(provider_stream, disconnect_event):
                        if not first_token_seen:
                            first_token_seen = True
                            _log_stream_phase(
                                "generation.provider.first_token",
                                request_id=request_id,
                                conversation_id=conversation.id,
                                tenant_id=self.context.tenant_id,
                                provider=stream_result.get("provider"),
                                model=stream_result.get("model"),
                                elapsed_ms=(time.monotonic() - stream_started_at) * 1000,
                            )
                        full_text += token
                        yield _sse({"type": "token", "text": token})
                except _ClientDisconnected:
                    _log_stream_phase(
                        "generation.client_disconnect",
                        request_id=request_id,
                        conversation_id=conversation.id,
                        tenant_id=self.context.tenant_id,
                        provider=stream_result.get("provider"),
                        model=stream_result.get("model"),
                        elapsed_ms=(time.monotonic() - stream_started_at) * 1000,
                    )
                    _log_stream_phase(
                        "generation.cancelled",
                        request_id=request_id,
                        conversation_id=conversation.id,
                        tenant_id=self.context.tenant_id,
                        outcome="client_disconnect",
                    )
                    # Deliberately not caught by `except Exception` below: no
                    # error frame, no done frame, no persistence — the
                    # generator unwinds through the caller's `async with
                    # session.begin()`, which rolls back the not-yet-committed
                    # user message / ai_request flush exactly as it already
                    # does for a Starlette-detected disconnect.
                    raise
                except Exception:
                    yield _sse({"type": "error", "detail": "The AI provider could not complete the response. Please try again."})
                    return

            _log_stream_phase(
                "generation.persistence.start",
                request_id=request_id,
                conversation_id=conversation.id,
                tenant_id=self.context.tenant_id,
                elapsed_ms=(time.monotonic() - stream_started_at) * 1000,
            )
            # Post-generation: persist everything with the completed text
                # Wrap in a routed response equivalent for reuse of existing persistence logic
                from ..ai.router import RoutedResponse
                from ..ai.contracts import ProviderResponse, ProviderAttempt
                actual_provider = stream_result.get("provider") or "streamed"
                actual_model = stream_result.get("model") or "streamed"
                fake_routed = RoutedResponse(
                    response=ProviderResponse(
                        provider=actual_provider,
                        model=actual_model,
                        text=full_text,
                        finish_reason="stop",
                        latency_ms=0,
                    ),
                    attempts=[ProviderAttempt(provider=actual_provider, model=actual_model, status="completed", reason="stream_mode")],
                    routing_reason="stream_mode",
                )

                combined_sources = self._merge_sources(sources, [])
                integrity = self.integrity_guard.validate(full_text, combined_sources)
                integrity_warnings = [*retrieval_warnings, *integrity.warnings]

                model_execution_id = await self._record_model_attempts(ai_request.id, fake_routed)
                await usage_governance.record_usage(
                    provider=actual_provider,
                    model_id=actual_model,
                    task_type=classification.task_type.value,
                    status_code="completed",
                    input_tokens=None,
                    output_tokens=None,
                    latency_ms=0,
                    currency_code=usage_decision.currency_code,
                )

                # Extract pending_action block from AI response and store server-side
                pending_action_token: str | None = None
                pending_action_label: str = ""
                pending_action_details: list[dict] = []
                clean_text, pending_block = self._extract_pending_action(integrity.text)
                if pending_block:
                    from .pending_actions import PendingActionStore
                    store = PendingActionStore.get()
                    resolved = await self._resolve_pending_action_block(pending_block)
                    if resolved:
                        pending_action_token = await store.create(
                            user_id=self.context.user_id,
                            tenant_id=self.context.tenant_id,
                            action_type=resolved["action_type"],
                            payload=resolved["payload"],
                            label=resolved["label"],
                            details=resolved["details"],
                        )
                        pending_action_label = resolved["label"]
                        pending_action_details = resolved["details"]
                        # Replace integrity text with clean version (block removed)
                        integrity = integrity._replace(text=clean_text) if hasattr(integrity, "_replace") else type(integrity)(text=clean_text, warnings=integrity.warnings, cited_source_keys=integrity.cited_source_keys)
                # Use server-side token pre-created by CapabilityRegistry (write path)
                if not pending_action_token and capability_result.pending_action_token:
                    pending_action_token = capability_result.pending_action_token
                    pending_action_label = capability_result.pending_action_label
                    pending_action_details = capability_result.pending_action_details

                title = self._title_from_output(integrity.text, payload.content)
                generated_output = GeneratedOutput(
                    id=uuid4(),
                    tenant_id=self.context.tenant_id,
                    conversation_id=conversation.id,
                    source_message_id=user_message.id,
                    ai_request_id=ai_request.id,
                    output_type=classification.task_type.value,
                    title=title,
                    is_formally_approved=False,
                    approval_disclaimer=(
                        "AI-generated draft requiring authorised human review before formal use."
                        if classification.human_review_required
                        else "AI-generated teaching support output; lecturer review is recommended."
                    ),
                )
                self.session.add(generated_output)
                await self.session.flush()

                module_context_data = module_bundle.as_dict() if module_bundle else None
                structured_content = self.output_workflow.structure(
                    task_type=classification.task_type,
                    markdown=integrity.text,
                    classification=classification.model_dump(mode="json"),
                    module_context=module_context_data,
                )

                safety_evaluation = self.safety.evaluate(
                    task_type=classification.task_type,
                    content=integrity.text,
                    detected_total_marks=(
                        int(classification.detected_entities["total_marks"])
                        if classification.detected_entities.get("total_marks") is not None
                        else None
                    ),
                    module_context_available=module_bundle is not None,
                )
                integrity_warnings.extend(
                    warning for warning in safety_evaluation.warnings if warning not in integrity_warnings
                )

                output_version = OutputVersion(
                    id=uuid4(),
                    tenant_id=self.context.tenant_id,
                    generated_output_id=generated_output.id,
                    version_number=1,
                    previous_version_id=None,
                    created_by_user_id=self.context.user_id,
                    model_execution_id=model_execution_id,
                    content_text=integrity.text,
                    structured_content=structured_content,
                    change_reason="Initial AI-generated streamed output",
                )
                self.session.add(output_version)
                await self.session.flush()
                generated_output.current_version_id = output_version.id

                lifecycle = OutputLifecycle(
                    id=uuid4(),
                    tenant_id=self.context.tenant_id,
                    generated_output_id=generated_output.id,
                    owner_user_id=self.context.user_id,
                    module_id=(module_bundle.module_id if module_bundle else conversation.module_id),
                    module_offering_id=(module_bundle.module_offering_id if module_bundle else None),
                    workflow_status="draft",
                    risk_level=safety_evaluation.risk_level.value,
                    assessment_kind=(
                        classification.task_type.value
                        if safety_evaluation.risk_level.value != "none"
                        else None
                    ),
                    review_required=(
                        classification.human_review_required
                        or safety_evaluation.risk_level.value != "none"
                    ),
                    answer_key_present=safety_evaluation.answers_detected,
                    student_release_allowed=safety_evaluation.student_copy_safe,
                    policy_snapshot={
                        "assessment_safety_version": self.safety.VERSION,
                        "workflow_version": self.output_workflow.VERSION,
                        "privacy_classification": classification.privacy_classification.value,
                    },
                )
                safety_review = AssessmentSafetyReview(
                    id=uuid4(),
                    tenant_id=self.context.tenant_id,
                    generated_output_id=generated_output.id,
                    output_version_id=output_version.id,
                    status=safety_evaluation.status.value,
                    risk_level=safety_evaluation.risk_level.value,
                    checks=safety_evaluation.checks,
                    warnings=safety_evaluation.warnings,
                    blocked_reasons=safety_evaluation.blocked_reasons,
                    answers_detected=safety_evaluation.answers_detected,
                    personal_data_detected=safety_evaluation.personal_data_detected,
                    student_copy_safe=safety_evaluation.student_copy_safe,
                )
                workflow_action = OutputWorkflowAction(
                    id=uuid4(),
                    tenant_id=self.context.tenant_id,
                    generated_output_id=generated_output.id,
                    output_version_id=output_version.id,
                    action="created",
                    previous_status=None,
                    new_status="draft",
                    performed_by_user_id=self.context.user_id,
                    active_role_code=self.context.role_code,
                    reason="Initial AI-generated streamed output created in the unified conversation.",
                    action_metadata={"safety_status": safety_evaluation.status.value},
                )
                self.session.add_all([lifecycle, safety_review, workflow_action])
                await self.session.flush()

                assistant_message = Message(
                    id=uuid4(),
                    tenant_id=self.context.tenant_id,
                    conversation_id=conversation.id,
                    author_user_id=None,
                    role="assistant",
                    sequence_number=next_sequence + 1,
                    content_text=integrity.text,
                    content_blocks=[
                        {
                            "type": "inline_output",
                            "output_type": classification.task_type.value,
                            "title": title,
                            "editable": True,
                            "generated_output_id": str(generated_output.id),
                            "output_version_id": str(output_version.id),
                            "version_number": 1,
                            "workflow_status": lifecycle.workflow_status,
                            "risk_level": lifecycle.risk_level,
                            "safety_status": safety_review.status,
                            "requires_human_review": lifecycle.review_required,
                            "approval_disclaimer": generated_output.approval_disclaimer,
                        }
                    ],
                    parent_message_id=user_message.id,
                )
                self.session.add(assistant_message)
                await self.session.flush()

                source_cards = await self._persist_sources_and_citations(
                    ai_request_id=ai_request.id,
                    output_version_id=output_version.id,
                    sources=combined_sources,
                    cited_source_keys=set(integrity.cited_source_keys),
                )

                if conversation.title == "New teaching conversation":
                    conversation.title = self._title_from_request(payload.content)

                await self.audit.record(
                    action="ai.response_streamed",
                    resource_type="generated_output",
                    resource_id=generated_output.id,
                    metadata={
                        "task_type": classification.task_type.value,
                        "provider": "streamed",
                        "source_count": len(source_cards),
                        "workflow_status": lifecycle.workflow_status,
                        "safety_status": safety_review.status,
                    },
                )
                await self.session.flush()
                await self.session.refresh(conversation)

                _log_stream_phase(
                    "generation.persistence.complete",
                    request_id=request_id,
                    conversation_id=conversation.id,
                    tenant_id=self.context.tenant_id,
                    provider=stream_result.get("provider"),
                    model=stream_result.get("model"),
                    elapsed_ms=(time.monotonic() - stream_started_at) * 1000,
                )
                _log_stream_phase(
                    "generation.done",
                    request_id=request_id,
                    conversation_id=conversation.id,
                    tenant_id=self.context.tenant_id,
                    provider=stream_result.get("provider"),
                    model=stream_result.get("model"),
                    elapsed_ms=(time.monotonic() - stream_started_at) * 1000,
                    outcome="success",
                )
                yield _sse({
                    "type": "done",
                    "conversation_id": str(conversation.id),
                    "conversation_title": conversation.title,
                    "user_message_id": str(user_message.id),
                    "assistant_message_id": str(assistant_message.id),
                    "output_type": classification.task_type.value,
                    "title": title,
                    "generated_output_id": str(generated_output.id),
                    "output_version_id": str(output_version.id),
                    "version_number": 1,
                    "workflow_status": lifecycle.workflow_status,
                    "risk_level": lifecycle.risk_level,
                    "safety_status": safety_review.status,
                    "requires_human_review": lifecycle.review_required,
                    "approval_disclaimer": generated_output.approval_disclaimer,
                    "provider": actual_provider,
                    "model": actual_model,
                    "requested_provider": ai_selection.requested_provider,
                    "requested_model": ai_selection.requested_model,
                    "integrity_warnings": integrity_warnings,
                    "pending_action_token": pending_action_token,
                    "pending_action_label": pending_action_label,
                    "pending_action_details": pending_action_details,
                    "sources": [
                        {
                            "number": card.number,
                            "source_key": card.source_key,
                            "title": card.title,
                            "authors": card.authors,
                            "publisher_or_organisation": card.publisher_or_organisation,
                            "publication_date": card.publication_date,
                            "url": card.url,
                            "doi": card.doi,
                            "verified_retrieval": card.verified_retrieval,
                            "cited_in_response": card.cited_in_response,
                            "source_kind": card.source_kind,
                            "institutional": card.institutional,
                            "document_version_id": card.document_version_id,
                            "locator": card.locator,
                            "access_label": card.access_label,
                        }
                        for card in source_cards
                    ],
                })

        except HTTPException as exc:
            _log_stream_phase(
                "generation.error",
                request_id=request_id,
                conversation_id=conversation_id,
                tenant_id=self.context.tenant_id,
                outcome="http_exception",
                elapsed_ms=(time.monotonic() - stream_started_at) * 1000,
            )
            yield _sse({"type": "error", "detail": exc.detail if isinstance(exc.detail, str) else "Permission denied."})
        except Exception as _exc:
            import logging as _logging
            _logging.getLogger("lsa.engine").exception("Unhandled error in stream_response: %s", _exc)
            _log_stream_phase(
                "generation.error",
                request_id=request_id,
                conversation_id=conversation_id,
                tenant_id=self.context.tenant_id,
                outcome="unhandled_exception",
                elapsed_ms=(time.monotonic() - stream_started_at) * 1000,
            )
            yield _sse({"type": "error", "detail": "An unexpected error occurred. Please try again."})
        finally:
            if watcher_task is not None:
                watcher_task.cancel()
                with contextlib.suppress(BaseException):
                    await watcher_task

    # ------------------------------------------------------------------
    # Pending action helpers
    # ------------------------------------------------------------------

    _PENDING_BLOCK_RE = re.compile(
        r"```pending_action\s*\n(.*?)```",
        re.DOTALL,
    )

    def _extract_pending_action(self, text: str) -> tuple[str, dict | None]:
        """Return (cleaned_text, parsed_block_dict | None)."""
        m = self._PENDING_BLOCK_RE.search(text)
        if not m:
            return text, None
        block_text = m.group(1)
        parsed: dict[str, str] = {}
        for line in block_text.strip().splitlines():
            if ":" in line:
                k, _, v = line.partition(":")
                parsed[k.strip()] = v.strip()
        clean = self._PENDING_BLOCK_RE.sub("", text).strip()
        return clean, parsed if parsed else None

    async def _resolve_pending_action_block(self, block: dict) -> dict | None:
        """Validate and enrich the AI-produced block into a server-side payload."""
        action = block.get("action", "")

        if action == "assign_lecturer":
            try:
                lid = UUID(block["lecturer_id"])
                mid = UUID(block["module_offering_id"])
            except (KeyError, ValueError):
                return None
            # Verify both belong to this tenant
            from sqlalchemy import select
            from services.database.models.academics import ModuleOffering
            from services.database.models.identity import User, Membership
            user = await self.session.scalar(
                select(User)
                .join(Membership, (Membership.user_id == User.id) & (Membership.tenant_id == self.context.tenant_id))
                .where(User.id == lid)
            )
            offering = await self.session.scalar(
                select(ModuleOffering).where(
                    ModuleOffering.id == mid,
                    ModuleOffering.tenant_id == self.context.tenant_id,
                )
            )
            if not user or not offering:
                return None
            return {
                "action_type": "assign_lecturer",
                "label": "Confirm Lecturer Assignment",
                "details": [
                    {"key": "Lecturer", "value": block.get("lecturer_name", str(lid))},
                    {"key": "Module", "value": block.get("module_label", str(mid))},
                    {"key": "Role", "value": "Lecturer"},
                ],
                "payload": {
                    "lecturer_user_id": str(lid),
                    "module_offering_id": str(mid),
                    "lecturer_name": block.get("lecturer_name", ""),
                    "module_label": block.get("module_label", ""),
                },
            }

        if action == "create_org_unit":
            try:
                type_id = UUID(block["unit_type_id"])
                code = block["code"]
                name = block["name"]
                parent_raw = block.get("parent_id", "NONE")
                parent_id = None if parent_raw in ("NONE", "", "null") else str(UUID(parent_raw))
            except (KeyError, ValueError):
                return None
            return {
                "action_type": "create_org_unit",
                "label": "Confirm Create Organisational Unit",
                "details": [
                    {"key": "Name", "value": name},
                    {"key": "Code", "value": code},
                    {"key": "Parent", "value": parent_id or "(root)"},
                ],
                "payload": {
                    "unit_type_id": str(type_id),
                    "parent_id": parent_id or "NONE",
                    "code": code,
                    "name": name,
                },
            }

        return None

    _KNOWN_PROVIDERS = {"openai", "anthropic", "google_gemini", "deepseek", "ollama"}
    _UNAVAILABLE_MODEL_DETAIL = "The selected model is currently unavailable. Choose another model or switch to Auto."

    @dataclass(slots=True)
    class AISelection:
        allowed_providers: set[str] | None
        denied_providers: set[str] | None
        model_override: str | None
        requested_provider: str
        requested_model: str
        persist: dict | None

    def _resolve_ai_selection(
        self,
        conversation: Conversation,
        payload: MessageCreate,
        usage_decision: object,
    ) -> "ConversationEngine.AISelection":
        """Intersect the user's explicit provider+model choice with governance policy.

        Distinguishes PROVIDER from MODEL: an explicit choice pins the request to
        exactly one provider and (if given) one model id on that provider — never
        a silent substitute. Raises HTTPException(409) if governance/config makes
        the explicit choice unavailable, and HTTPException(400) for an unknown
        provider name, so the caller never silently falls back.
        """
        governance_allowed = set(usage_decision.allowed_providers) if usage_decision.allowed_providers else None
        governance_denied = set(usage_decision.denied_providers) if usage_decision.denied_providers else None

        requested_provider = payload.preferred_provider
        requested_model = payload.preferred_model
        explicit_request = requested_provider is not None

        if not explicit_request:
            stored = conversation.context.get("ai_selection") or {}
            if stored.get("mode") == "explicit":
                requested_provider = stored.get("provider")
                requested_model = stored.get("model")

        if requested_provider in (None, "auto", ""):
            persist = {"mode": "auto"} if explicit_request else None
            return self.AISelection(governance_allowed, governance_denied, None, "auto", "auto", persist)

        if requested_provider not in self._KNOWN_PROVIDERS:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=f"Unknown model '{requested_provider}'.")
        provider_instance = self.router.providers.get(requested_provider)
        if provider_instance is None or not provider_instance.configured:
            raise HTTPException(status.HTTP_409_CONFLICT, detail=self._UNAVAILABLE_MODEL_DETAIL)
        if governance_allowed is not None and requested_provider not in governance_allowed:
            raise HTTPException(status.HTTP_409_CONFLICT, detail=self._UNAVAILABLE_MODEL_DETAIL)
        if governance_denied is not None and requested_provider in governance_denied:
            raise HTTPException(status.HTTP_409_CONFLICT, detail=self._UNAVAILABLE_MODEL_DETAIL)

        model_to_use = requested_model or provider_instance.default_model
        persist = (
            {"mode": "explicit", "provider": requested_provider, "model": model_to_use}
            if explicit_request else None
        )
        return self.AISelection(
            {requested_provider}, None, model_to_use, requested_provider, model_to_use, persist,
        )

    async def _require_ai_permission(self) -> None:
        await AuthorizationService(self.session, self.context).require_permission(
            tenant_id=self.context.tenant_id,
            user_id=self.context.user_id,
            permission_code="ai.use",
        )

    async def _owned_conversation(self, conversation_id: UUID, *, allow_deleted: bool = False) -> Conversation:
        conversation = await self.session.scalar(
            select(Conversation).where(
                Conversation.tenant_id == self.context.tenant_id,
                Conversation.id == conversation_id,
                Conversation.owner_user_id == self.context.user_id,
            )
        )
        if conversation is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found.")
        if not allow_deleted and conversation.context.get("deleted_at"):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found.")
        return conversation

    async def _history(self, conversation_id: UUID) -> list[ChatMessage]:
        rows = list(
            await self.session.scalars(
                select(Message)
                .where(
                    Message.tenant_id == self.context.tenant_id,
                    Message.conversation_id == conversation_id,
                    Message.is_redacted.is_(False),
                )
                .order_by(Message.sequence_number.desc())
                .limit(self.settings.ai_max_conversation_messages)
            )
        )
        rows.reverse()
        return [
            ChatMessage(role=ChatRole(row.role), content=row.content_text)
            for row in rows
            if row.role in {"user", "assistant"} and row.content_text
        ]

    async def _discover_sources(
        self, query: str, classification: TaskClassification
    ) -> list[SourceCandidate]:
        if not classification.source_verification_required:
            return []
        return await self.source_discovery.discover(query)

    async def _record_model_attempts(self, ai_request_id: UUID, routed: RoutedResponse) -> UUID | None:
        completed_id: UUID | None = None
        now = datetime.now(timezone.utc)
        for number, attempt in enumerate(routed.attempts, start=1):
            execution = ModelExecution(
                id=uuid4(),
                tenant_id=self.context.tenant_id,
                ai_request_id=ai_request_id,
                provider=attempt.provider,
                model_id=attempt.model or "unconfigured",
                routing_reason=attempt.reason,
                attempt_number=number,
                input_tokens=(routed.response.input_tokens if attempt.status == "completed" else None),
                output_tokens=(routed.response.output_tokens if attempt.status == "completed" else None),
                latency_ms=attempt.latency_ms,
                estimated_cost=None,
                status=attempt.status,
                error_code=attempt.error_code,
                started_at=now,
                completed_at=now,
                execution_metadata={
                    "router_reason": routed.routing_reason,
                    "provider_request_id": routed.response.request_id if attempt.status == "completed" else None,
                },
            )
            self.session.add(execution)
            if attempt.status == "completed":
                completed_id = execution.id
        await self.session.flush()
        return completed_id

    async def _persist_sources_and_citations(
        self,
        *,
        ai_request_id: UUID,
        output_version_id: UUID,
        sources: list[SourceCandidate],
        cited_source_keys: set[str],
    ) -> list[SourceCard]:
        integrity_service = SourceIntegrityService(self.session, self.context)
        cards: list[SourceCard] = []
        for number, candidate in enumerate(sources, start=1):
            retrieval = await integrity_service.record_retrieval(
                ai_request_id=ai_request_id,
                source_type=candidate.source_type,
                title=candidate.title,
                authors=candidate.authors,
                publisher_or_organisation=candidate.publisher_or_organisation,
                publication_date=candidate.publication_date,
                canonical_url=str(candidate.canonical_url) if candidate.canonical_url else None,
                doi=candidate.doi,
                licence=candidate.licence,
                reliability_tier=candidate.reliability_tier,
                is_institutional=bool(candidate.metadata.get("is_institutional")),
                is_restricted=bool(candidate.metadata.get("is_restricted")),
                retrieved_by=candidate.retrieved_by,
                retrieval_query=candidate.retrieval_query,
                rank=candidate.rank,
                relevance_score=(str(candidate.relevance_score) if candidate.relevance_score is not None else None),
                access_snapshot=candidate.metadata,
                stable_key=(
                    f"document-version:{candidate.metadata['document_version_id']}"
                    if candidate.metadata.get("document_version_id")
                    else None
                ),
            )
            cited = candidate.source_key in cited_source_keys
            if cited:
                citation = await integrity_service.create_citation(
                    output_version_id=output_version_id,
                    source_retrieval_id=retrieval.id,
                    citation_number=number,
                    display_label=candidate.title,
                )
                await integrity_service.record_verification(
                    citation_id=citation.id,
                    status="partially_verified",
                    verifier="citation_integrity_guard_v1",
                    findings={
                        "retrieval_verified": True,
                        "identifier_allowed": True,
                        "claim_entailment_requires_evaluation": True,
                    },
                )
            cards.append(
                SourceCard(
                    number=number,
                    source_key=candidate.source_key,
                    title=candidate.title,
                    authors=candidate.authors,
                    publisher_or_organisation=candidate.publisher_or_organisation,
                    publication_date=candidate.publication_date,
                    url=str(candidate.canonical_url) if candidate.canonical_url else None,
                    doi=candidate.doi,
                    verified_retrieval=True,
                    cited_in_response=cited,
                    source_kind=("institutional" if candidate.metadata.get("is_institutional") else "external"),
                    institutional=bool(candidate.metadata.get("is_institutional")),
                    document_version_id=candidate.metadata.get("document_version_id"),
                    locator=candidate.metadata.get("locator"),
                    access_label=("Restricted institutional source" if candidate.metadata.get("is_restricted") else None),
                )
            )
        return cards

    @staticmethod
    def _merge_sources(primary: list[SourceCandidate], secondary: list[SourceCandidate]) -> list[SourceCandidate]:
        merged: dict[str, SourceCandidate] = {}
        for source in [*primary, *secondary]:
            identity = (source.doi or str(source.canonical_url or source.source_key)).lower()
            merged.setdefault(identity, source)
        return list(merged.values())[:10]

    @staticmethod
    def _title_from_output(text: str, request: str) -> str:
        match = re.search(r"^#\s+(.+)$", text, re.MULTILINE)
        return match.group(1).strip()[:500] if match else ConversationEngine._title_from_request(request)

    @staticmethod
    def _title_from_request(request: str) -> str:
        compact = re.sub(r"\s+", " ", request).strip()
        return compact[:80] + ("…" if len(compact) > 80 else "")
