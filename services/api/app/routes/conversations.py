from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from fastapi.responses import StreamingResponse
from typing import Annotated

from ..ai.router import ModelRouter
from ..core.dependencies import CurrentContext, DatabaseSession
from ..core.settings import get_settings
from ..dependencies import get_embedding_client, get_qdrant_gateway
from ..ingestion.embeddings import EmbeddingClient
from ..integrations.qdrant import QdrantGateway
from ..schemas.conversations import (
    ConversationCreate,
    ConversationDetail,
    ConversationRead,
    ConversationUpdate,
    MessageCreate,
    MessageRead,
    ProviderStatusRead,
    UnifiedAIResponse,
)
from ..services.conversation_engine import ConversationEngine
from ..services.document_retrieval import DocumentRetrievalService

router = APIRouter(prefix="/conversations", tags=["unified AI work area"])


@router.post("", response_model=ConversationRead, status_code=status.HTTP_201_CREATED)
async def create_conversation(
    payload: ConversationCreate,
    session: DatabaseSession,
    context: CurrentContext,
) -> ConversationRead:
    conversation = await ConversationEngine(session, context, get_settings()).create_conversation(payload)
    return ConversationRead.model_validate(conversation)


@router.get("", response_model=list[ConversationRead])
async def list_conversations(
    session: DatabaseSession,
    context: CurrentContext,
    limit: int = Query(default=50, ge=1, le=100),
) -> list[ConversationRead]:
    rows = await ConversationEngine(session, context, get_settings()).list_conversations(limit=limit)
    return [ConversationRead.model_validate(row) for row in rows]


@router.get("/providers", response_model=list[ProviderStatusRead])
async def provider_status(
    session: DatabaseSession,
    context: CurrentContext,
) -> list[ProviderStatusRead]:
    engine = ConversationEngine(session, context, get_settings())
    await engine._require_ai_permission()
    return [ProviderStatusRead.model_validate(item) for item in ModelRouter(get_settings()).status()]


@router.get("/{conversation_id}", response_model=ConversationDetail)
async def get_conversation(
    conversation_id: UUID,
    session: DatabaseSession,
    context: CurrentContext,
) -> ConversationDetail:
    conversation, messages = await ConversationEngine(session, context, get_settings()).get_conversation(conversation_id)
    return ConversationDetail(
        conversation=ConversationRead.model_validate(conversation),
        messages=[MessageRead.model_validate(message) for message in messages],
    )


@router.patch("/{conversation_id}", response_model=ConversationRead)
async def update_conversation(
    conversation_id: UUID,
    payload: ConversationUpdate,
    session: DatabaseSession,
    context: CurrentContext,
) -> ConversationRead:
    row = await ConversationEngine(session, context, get_settings()).update_conversation(conversation_id, payload)
    return ConversationRead.model_validate(row)


@router.delete("/{conversation_id}", response_model=ConversationRead)
async def archive_conversation(
    conversation_id: UUID,
    session: DatabaseSession,
    context: CurrentContext,
) -> ConversationRead:
    row = await ConversationEngine(session, context, get_settings()).archive_conversation(conversation_id)
    return ConversationRead.model_validate(row)


@router.post("/{conversation_id}/messages/stream")
async def stream_message(
    conversation_id: UUID,
    payload: MessageCreate,
    session: DatabaseSession,
    context: CurrentContext,
    embedding: Annotated[EmbeddingClient, Depends(get_embedding_client)],
    qdrant: Annotated[QdrantGateway, Depends(get_qdrant_gateway)],
) -> StreamingResponse:
    engine = ConversationEngine(
        session,
        context,
        get_settings(),
        document_retrieval=DocumentRetrievalService(
            session, context, embedding_client=embedding, qdrant=qdrant, settings=get_settings()
        ),
    )
    return StreamingResponse(
        engine.stream_message(conversation_id=conversation_id, payload=payload),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post("/{conversation_id}/messages", response_model=UnifiedAIResponse)
async def create_message(
    conversation_id: UUID,
    payload: MessageCreate,
    session: DatabaseSession,
    context: CurrentContext,
    embedding: Annotated[EmbeddingClient, Depends(get_embedding_client)],
    qdrant: Annotated[QdrantGateway, Depends(get_qdrant_gateway)],
) -> UnifiedAIResponse:
    (
        conversation,
        user_message,
        assistant_message,
        classification,
        output,
        source_cards,
        routed,
        warnings,
    ) = await ConversationEngine(
        session,
        context,
        get_settings(),
        document_retrieval=DocumentRetrievalService(
            session, context, embedding_client=embedding, qdrant=qdrant, settings=get_settings()
        ),
    ).submit_message(conversation_id=conversation_id, payload=payload)
    return UnifiedAIResponse(
        conversation=ConversationRead.model_validate(conversation),
        user_message=user_message,
        assistant_message=assistant_message,
        classification=classification,
        output=output,
        sources=source_cards,
        integrity_warnings=warnings,
        provider=routed.response.provider,
        model=routed.response.model,
        provider_attempts=routed.attempts,
        generated_at=datetime.now(timezone.utc),
    )
