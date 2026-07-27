from __future__ import annotations

import json
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy import func, select

from services.database.models import (
    Document, DocumentChunk, DocumentVersion, DocumentVersionTransition,
    ExtractedContent, IngestionJob
)

from ..core.dependencies import CurrentContext, DatabaseSession
from ..core.settings import get_settings
from ..dependencies import get_embedding_client, get_object_storage, get_qdrant_gateway
from ..ingestion.embeddings import EmbeddingClient
from ..integrations.object_storage import ObjectStorage
from ..integrations.qdrant import QdrantGateway
from ..schemas.documents import (
    DocumentResponse,
    DocumentVersionResponse,
    DocumentVersionTransitionRequest,
    DocumentVersionTransitionResponse,
    SingleUploadMetadata,
    UploadResponse,
    VersionHistoryResponse,
)
from ..schemas.ingestion import (
    ProcessDocumentRequest,
    ProcessDocumentResponse,
    ProcessingStatusResponse,
)
from ..services.authorization import AuthorizationService
from ..services.document_access import DocumentAccessService
from ..services.document_ingestion import DocumentIngestionService
from ..services.document_versioning import DocumentVersioningService

router = APIRouter(prefix="/documents", tags=["documents and ingestion"])


@router.get("", response_model=list[DocumentResponse])
async def list_documents(session: DatabaseSession, context: CurrentContext) -> list[Document]:
    await AuthorizationService(session, context).require_permission(
        tenant_id=context.tenant_id, user_id=context.user_id, permission_code="content.read"
    )
    candidates = list(
        (
            await session.scalars(
                select(Document)
                .where(
                    Document.tenant_id == context.tenant_id,
                    Document.is_deleted.is_(False),
                    Document.current_version_id.is_not(None),
                )
                .order_by(Document.updated_at.desc())
                .limit(250)
            )
        ).all()
    )
    visible: list[Document] = []
    access = DocumentAccessService(session, context)
    for document in candidates:
        try:
            await access.require_version(document.current_version_id)
        except HTTPException as exc:
            if exc.status_code in {403, 404}:
                continue
            raise
        visible.append(document)
        if len(visible) >= 100:
            break
    return visible


@router.post("/upload", response_model=UploadResponse, status_code=status.HTTP_201_CREATED)
async def upload_document(
    session: DatabaseSession,
    context: CurrentContext,
    file: Annotated[UploadFile, File()],
    metadata_json: Annotated[str, Form()],
    storage: Annotated[ObjectStorage, Depends(get_object_storage)],
    embedding: Annotated[EmbeddingClient, Depends(get_embedding_client)],
    qdrant: Annotated[QdrantGateway, Depends(get_qdrant_gateway)],
) -> UploadResponse:
    try:
        metadata = SingleUploadMetadata.model_validate(json.loads(metadata_json))
    except (json.JSONDecodeError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=f"Invalid metadata_json: {exc}") from exc
    scope_type = "module" if metadata.module_id else "organisational_unit" if metadata.org_unit_id else "institution"
    scope_id: UUID | None = metadata.module_id or metadata.org_unit_id
    await AuthorizationService(session, context).require_permission(
        tenant_id=context.tenant_id,
        user_id=context.user_id,
        permission_code="content.upload",
        scope_type=scope_type,
        scope_id=scope_id,
    )
    content = await file.read()
    if len(content) > get_settings().maximum_upload_bytes:
        raise HTTPException(status_code=413, detail="The file exceeds the configured upload limit.")
    try:
        result = await DocumentVersioningService(session=session, storage=storage, context=context).create_version(
            title=metadata.title,
            document_type=metadata.document_type,
            filename=file.filename or "upload.bin",
            content=content,
            media_type=file.content_type,
            change_reason=metadata.change_reason,
            visibility=metadata.visibility,
            document_id=metadata.existing_document_id,
            org_unit_id=metadata.org_unit_id,
            programme_id=metadata.programme_id,
            module_id=metadata.module_id,
        )
        if not result.exact_duplicate and get_settings().ingestion_auto_process_uploads:
            await DocumentIngestionService(
                session,
                storage,
                context,
                embedding_client=embedding,
                qdrant=qdrant,
            ).process_version(result.version.id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return UploadResponse(
        document=DocumentResponse.model_validate(result.document),
        version=DocumentVersionResponse.model_validate(result.version),
        exact_duplicate=result.exact_duplicate,
    )


@router.get("/{document_id}/versions", response_model=VersionHistoryResponse)
async def version_history(
    document_id: UUID, session: DatabaseSession, context: CurrentContext
) -> VersionHistoryResponse:
    document = await session.scalar(
        select(Document).where(Document.tenant_id == context.tenant_id, Document.id == document_id)
    )
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found.")
    if document.current_version_id is not None:
        await DocumentAccessService(session, context).require_version(document.current_version_id)
    await AuthorizationService(session, context).require_permission(
        tenant_id=context.tenant_id,
        user_id=context.user_id,
        permission_code="content.read",
        scope_type="module" if document.module_id else "programme" if document.programme_id else "organisational_unit" if document.org_unit_id else "institution",
        scope_id=document.module_id or document.programme_id or document.org_unit_id,
    )
    versions = list(
        await session.scalars(
            select(DocumentVersion)
            .where(DocumentVersion.tenant_id == context.tenant_id, DocumentVersion.document_id == document.id)
            .order_by(DocumentVersion.version_number.desc())
        )
    )
    return VersionHistoryResponse(
        document=DocumentResponse.model_validate(document),
        versions=[DocumentVersionResponse.model_validate(item) for item in versions],
    )


@router.post("/versions/{version_id}/process", response_model=ProcessDocumentResponse)
async def process_document_version(
    version_id: UUID,
    payload: ProcessDocumentRequest,
    session: DatabaseSession,
    context: CurrentContext,
    storage: Annotated[ObjectStorage, Depends(get_object_storage)],
    embedding: Annotated[EmbeddingClient, Depends(get_embedding_client)],
    qdrant: Annotated[QdrantGateway, Depends(get_qdrant_gateway)],
) -> ProcessDocumentResponse:
    await DocumentAccessService(session, context).require_version(version_id)
    outcome = await DocumentIngestionService(
        session,
        storage,
        context,
        embedding_client=embedding,
        qdrant=qdrant,
    ).process_version(version_id, force=payload.force)
    return ProcessDocumentResponse(outcome=outcome)


@router.get("/versions/{version_id}/processing", response_model=ProcessingStatusResponse)
async def processing_status(
    version_id: UUID, session: DatabaseSession, context: CurrentContext
) -> ProcessingStatusResponse:
    accessible = await DocumentAccessService(session, context).require_version(version_id)
    extraction = await session.scalar(
        select(ExtractedContent).where(
            ExtractedContent.tenant_id == context.tenant_id,
            ExtractedContent.document_version_id == version_id,
        )
    )
    latest_job = await session.scalar(
        select(IngestionJob)
        .where(IngestionJob.tenant_id == context.tenant_id, IngestionJob.document_version_id == version_id)
        .order_by(IngestionJob.created_at.desc())
        .limit(1)
    )
    count = int(
        await session.scalar(
            select(func.count(DocumentChunk.id)).where(
                DocumentChunk.tenant_id == context.tenant_id,
                DocumentChunk.document_version_id == version_id,
            )
        )
        or 0
    )
    return ProcessingStatusResponse(
        document_version_id=version_id,
        extraction=extraction,
        latest_job=latest_job,
        chunk_count=count,
        indexed=accessible.version.indexed_at is not None,
    )


@router.patch(
    "/versions/{version_id}/status",
    response_model=DocumentVersionTransitionResponse,
)
async def transition_document_version_status(
    version_id: UUID,
    payload: DocumentVersionTransitionRequest,
    session: DatabaseSession,
    context: CurrentContext,
    storage: Annotated[ObjectStorage, Depends(get_object_storage)],
) -> DocumentVersionTransition:
    try:
        return await DocumentVersioningService(
            session=session, storage=storage, context=context
        ).transition_status(
            version_id=version_id, to_status=payload.to_status, reason=payload.reason
        )
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
