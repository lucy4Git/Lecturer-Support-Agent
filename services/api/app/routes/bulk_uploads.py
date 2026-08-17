from __future__ import annotations

import json
import mimetypes
from pathlib import Path
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy import select

from services.database.models import UploadBatch, UploadItem

from ..core.dependencies import CurrentContext, DatabaseSession
from ..core.settings import get_settings
from ..dependencies import get_malware_scanner, get_object_storage
from ..ingestion import ArchiveInspectionError, SafeZipExpander
from ..integrations.malware_scanner import MalwareScanner
from ..integrations.object_storage import ObjectStorage
from ..schemas.bulk_uploads import (
    BulkUploadItemResult,
    BulkUploadRequestMetadata,
    BulkUploadResponse,
    UploadBatchResponse,
)
from ..schemas.documents import DocumentVersionResponse
from ..services.authorization import AuthorizationService
from ..services.bulk_upload import BulkUploadEntry, BulkUploadService
from ..services.job_queue import JobQueueService

router = APIRouter(prefix="/bulk-uploads", tags=["contextual bulk uploads"])


@router.post("", response_model=BulkUploadResponse, status_code=status.HTTP_202_ACCEPTED)
async def create_bulk_upload(
    session: DatabaseSession,
    context: CurrentContext,
    files: Annotated[list[UploadFile], File()],
    metadata_json: Annotated[str, Form()],
    storage: Annotated[ObjectStorage, Depends(get_object_storage)],
    malware_scanner: Annotated[MalwareScanner, Depends(get_malware_scanner)],
) -> BulkUploadResponse:
    try:
        metadata = BulkUploadRequestMetadata.model_validate(json.loads(metadata_json))
    except (json.JSONDecodeError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=f"Invalid metadata_json: {exc}") from exc
    if len(files) != len(metadata.files):
        raise HTTPException(status_code=422, detail="files and metadata.files must have equal length")
    # scope_type=None means "any scope the caller holds suffices" (private conversation attachments)
    await AuthorizationService(session, context).require_permission(
        tenant_id=context.tenant_id,
        user_id=context.user_id,
        permission_code="content.bulk_upload",
        scope_type=metadata.scope_type,
        scope_id=metadata.scope_id if metadata.scope_type else None,
    )
    settings = get_settings()
    expander = SafeZipExpander(
        maximum_entries=settings.ingestion_max_archive_entries,
        maximum_total_uncompressed_bytes=settings.ingestion_max_archive_uncompressed_bytes,
        maximum_member_bytes=settings.ingestion_max_archive_member_bytes,
    )
    entries: list[BulkUploadEntry] = []
    for upload, file_metadata in zip(files, metadata.files, strict=True):
        content = await upload.read()
        filename = upload.filename or file_metadata.client_item_key
        try:
            scan = await malware_scanner.scan_bytes(content, filename=filename)
        except Exception as exc:
            if settings.malware_scan_enabled and settings.malware_scan_fail_closed:
                raise HTTPException(status_code=503, detail="Upload scanning is temporarily unavailable.") from exc
            scan = None
        if scan is not None and not scan.clean:
            raise HTTPException(status_code=422, detail=f"{filename} was rejected by malware scanning.")
        if len(content) > settings.maximum_upload_bytes:
            raise HTTPException(status_code=413, detail=f"{filename} exceeds the upload limit.")
        if metadata.expand_archives and Path(filename).suffix.lower() == ".zip":
            try:
                members = expander.expand(content)
            except ArchiveInspectionError as exc:
                raise HTTPException(status_code=422, detail=str(exc)) from exc
            for member in members:
                try:
                    member_scan = await malware_scanner.scan_bytes(member.content, filename=member.path)
                except Exception as exc:
                    if settings.malware_scan_enabled and settings.malware_scan_fail_closed:
                        raise HTTPException(status_code=503, detail="Archive member scanning is temporarily unavailable.") from exc
                    member_scan = None
                if member_scan is not None and not member_scan.clean:
                    raise HTTPException(status_code=422, detail=f"Archive member {member.path} was rejected by malware scanning.")
                media_type = mimetypes.guess_type(member.path)[0] or "application/octet-stream"
                entries.append(
                    BulkUploadEntry(
                        client_item_key=f"{file_metadata.client_item_key}:{member.path}",
                        filename=member.path,
                        content=member.content,
                        media_type=media_type,
                        title=Path(member.path).stem.replace("_", " "),
                        document_type=(file_metadata.document_type if file_metadata.document_type != "archive" else "teaching_material"),
                        change_reason=file_metadata.change_reason,
                        existing_document_id=None,
                        metadata={**file_metadata.metadata, "archive_source": filename, "archive_member": member.path},
                        visibility=metadata.visibility,
                    )
                )
        else:
            entries.append(
                BulkUploadEntry(
                    client_item_key=file_metadata.client_item_key,
                    filename=filename,
                    content=content,
                    media_type=upload.content_type,
                    title=file_metadata.title,
                    document_type=file_metadata.document_type,
                    change_reason=file_metadata.change_reason,
                    existing_document_id=file_metadata.existing_document_id,
                    metadata=file_metadata.metadata,
                    visibility=metadata.visibility,
                )
            )
    batch, results = await BulkUploadService(session, storage, context).create_batch(
        entries=entries,
        scope_type=metadata.scope_type,
        scope_id=metadata.scope_id,
        change_reason=metadata.change_reason,
        org_unit_id=metadata.org_unit_id,
        programme_id=metadata.programme_id,
        module_id=metadata.module_id,
    )
    # Enqueue background ingestion jobs — do NOT process synchronously in the request.
    # The existing content.ingest_document worker handler (services/worker/handlers.py)
    # claims each job, parses, chunks, embeds, and indexes to Qdrant.
    processing: list[dict] = []
    if metadata.auto_process:
        queue = JobQueueService(session)
        for result in results:
            if result.exact_duplicate:
                processing.append({"document_version_id": str(result.version.id), "status": "exact_duplicate"})
                continue
            job = await queue.enqueue(
                tenant_id=context.tenant_id,
                job_type="content.ingest_document",
                payload={
                    "document_version_id": str(result.version.id),
                    # Worker reconstructs the caller's context so DocumentAccessService
                    # uses the same role and scope that authorised the upload.
                    "requested_by_role_code": context.role_code,
                },
                requested_by_user_id=context.user_id,
                correlation_id=str(batch.id),
                idempotency_key=f"ingest:{result.version.id}",
            )
            processing.append({
                "document_version_id": str(result.version.id),
                "status": "queued",
                "job_id": str(job.id),
            })
    items = list(
        await session.scalars(
            select(UploadItem)
            .where(UploadItem.tenant_id == context.tenant_id, UploadItem.upload_batch_id == batch.id)
            .order_by(UploadItem.created_at)
        )
    )
    return BulkUploadResponse(
        batch=UploadBatchResponse.model_validate(batch),
        versions=[DocumentVersionResponse.model_validate(result.version) for result in results],
        items=[
            BulkUploadItemResult(
                client_item_key=item.client_item_key,
                original_filename=item.original_filename,
                status=item.status,
                document_version_id=item.document_version_id,
                validation_errors=item.validation_errors,
            )
            for item in items
        ],
        processing=processing,
    )


@router.get("/{batch_id}", response_model=BulkUploadResponse)
async def get_bulk_upload(
    batch_id: UUID, session: DatabaseSession, context: CurrentContext
) -> BulkUploadResponse:
    await AuthorizationService(session, context).require_permission(
        tenant_id=context.tenant_id, user_id=context.user_id, permission_code="content.read"
    )
    batch = await session.scalar(
        select(UploadBatch).where(
            UploadBatch.tenant_id == context.tenant_id,
            UploadBatch.id == batch_id,
            UploadBatch.uploaded_by_user_id == context.user_id,
        )
    )
    if batch is None:
        raise HTTPException(status_code=404, detail="Upload batch not found.")
    items = list(
        await session.scalars(
            select(UploadItem)
            .where(UploadItem.tenant_id == context.tenant_id, UploadItem.upload_batch_id == batch.id)
            .order_by(UploadItem.created_at)
        )
    )
    return BulkUploadResponse(
        batch=UploadBatchResponse.model_validate(batch),
        versions=[],
        items=[
            BulkUploadItemResult(
                client_item_key=item.client_item_key,
                original_filename=item.original_filename,
                status=item.status,
                document_version_id=item.document_version_id,
                validation_errors=item.validation_errors,
            )
            for item in items
        ],
        processing=[],
    )
