from __future__ import annotations

from io import BytesIO
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Response, status
from fastapi.responses import StreamingResponse

from services.database.models.enums import ExportAudience, ExportFormat

from ..core.dependencies import CurrentContext, DatabaseSession
from ..dependencies import get_object_storage
from ..integrations.object_storage import ObjectStorage
from ..schemas.teaching_outputs import (
    ExportCreate,
    ExportJobRead,
    OutputLifecycleRead,
    OutputVersionCreate,
    OutputVersionRead,
    RestoreVersionRequest,
    SafetyReviewRead,
    TeachingOutputRead,
    WorkflowActionRead,
    WorkflowTransitionRequest,
)
from ..services.generated_outputs import GeneratedOutputService
from ..services.teaching_output_exports import TeachingOutputExportService

router = APIRouter(prefix="/teaching-outputs", tags=["inline teaching outputs"])


def _output_read(output, lifecycle, version, safety) -> TeachingOutputRead:
    return TeachingOutputRead(
        id=output.id,
        conversation_id=output.conversation_id,
        source_message_id=output.source_message_id,
        output_type=output.output_type,
        title=output.title,
        current_version_id=output.current_version_id,
        is_formally_approved=output.is_formally_approved,
        approval_disclaimer=output.approval_disclaimer,
        lifecycle=OutputLifecycleRead.model_validate(lifecycle),
        current_version=OutputVersionRead.model_validate(version),
        safety_review=SafetyReviewRead.model_validate(safety),
    )


@router.get("/exports/{export_id}/download")
async def download_export(
    export_id: UUID,
    session: DatabaseSession,
    context: CurrentContext,
    storage: Annotated[ObjectStorage, Depends(get_object_storage)],
) -> StreamingResponse:
    job, stored = await TeachingOutputExportService(session, context, storage).require_download(export_id)
    content = await storage.get_bytes(
        object_key=stored.object_key, version_id=stored.storage_version_id
    )
    return StreamingResponse(
        BytesIO(content),
        media_type=job.media_type or "application/octet-stream",
        headers={"Content-Disposition": f'attachment; filename="{job.filename or "teaching-output"}"'},
    )


@router.get("/{output_id}", response_model=TeachingOutputRead)
async def get_teaching_output(
    output_id: UUID, session: DatabaseSession, context: CurrentContext
) -> TeachingOutputRead:
    return _output_read(*await GeneratedOutputService(session, context).get(output_id))


@router.get("/{output_id}/versions", response_model=list[OutputVersionRead])
async def list_output_versions(
    output_id: UUID, session: DatabaseSession, context: CurrentContext
) -> list[OutputVersionRead]:
    rows = await GeneratedOutputService(session, context).list_versions(output_id)
    return [OutputVersionRead.model_validate(row) for row in rows]


@router.post("/{output_id}/versions", response_model=TeachingOutputRead, status_code=status.HTTP_201_CREATED)
async def create_output_version(
    output_id: UUID,
    payload: OutputVersionCreate,
    session: DatabaseSession,
    context: CurrentContext,
) -> TeachingOutputRead:
    service = GeneratedOutputService(session, context)
    await service.create_version(
        output_id=output_id,
        content_markdown=payload.content_markdown,
        change_reason=payload.change_reason,
    )
    return _output_read(*await service.get(output_id))


@router.post("/{output_id}/versions/{source_version_id}/restore", response_model=TeachingOutputRead)
async def restore_output_version(
    output_id: UUID,
    source_version_id: UUID,
    payload: RestoreVersionRequest,
    session: DatabaseSession,
    context: CurrentContext,
) -> TeachingOutputRead:
    service = GeneratedOutputService(session, context)
    await service.restore_version(
        output_id=output_id, source_version_id=source_version_id, change_reason=payload.change_reason
    )
    return _output_read(*await service.get(output_id))


@router.post("/{output_id}/workflow", response_model=WorkflowActionRead)
async def transition_output(
    output_id: UUID,
    payload: WorkflowTransitionRequest,
    session: DatabaseSession,
    context: CurrentContext,
) -> WorkflowActionRead:
    _, action = await GeneratedOutputService(session, context).transition(
        output_id=output_id, action=payload.action, reason=payload.reason
    )
    return WorkflowActionRead.model_validate(action)


@router.get("/{output_id}/workflow", response_model=list[WorkflowActionRead])
async def output_workflow_history(
    output_id: UUID, session: DatabaseSession, context: CurrentContext
) -> list[WorkflowActionRead]:
    rows = await GeneratedOutputService(session, context).history(output_id)
    return [WorkflowActionRead.model_validate(row) for row in rows]


@router.post("/{output_id}/exports", response_model=ExportJobRead, status_code=status.HTTP_201_CREATED)
async def create_export(
    output_id: UUID,
    payload: ExportCreate,
    session: DatabaseSession,
    context: CurrentContext,
    storage: Annotated[ObjectStorage, Depends(get_object_storage)],
) -> ExportJobRead:
    job = await TeachingOutputExportService(session, context, storage).create(
        output_id=output_id,
        export_format=ExportFormat(payload.export_format),
        audience=ExportAudience(payload.audience),
        version_id=payload.version_id,
    )
    data = ExportJobRead.model_validate(job).model_dump()
    data["download_path"] = f"/api/v1/teaching-outputs/exports/{job.id}/download"
    return ExportJobRead(**data)


