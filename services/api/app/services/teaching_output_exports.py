from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID, uuid4

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from services.database.models import (
    AssessmentSafetyReview,
    ExportJob,
    GeneratedOutput,
    OutputLifecycle,
    OutputVersion,
    StorageObject,
)
from services.database.models.enums import ExportAudience, ExportFormat, ExportStatus, OutputWorkflowStatus

from ..ai.contracts import TeachingTaskType

from ..core.request_context import RequestContext
from ..integrations.object_storage import ObjectStorage
from .audit import AuditService
from .assessment_safety import AssessmentSafetyEvaluator
from .authorization import AuthorizationService
from .export_generation import ExportRenderer, safe_export_filename
from .generated_outputs import GeneratedOutputService


class TeachingOutputExportService:
    def __init__(
        self, session: AsyncSession, context: RequestContext, storage: ObjectStorage
    ) -> None:
        self.session = session
        self.context = context
        self.storage = storage
        self.authorization = AuthorizationService(session, context)
        self.audit = AuditService(session, context)
        self.renderer = ExportRenderer()
        self.safety_evaluator = AssessmentSafetyEvaluator()

    async def create(
        self,
        *,
        output_id: UUID,
        export_format: ExportFormat,
        audience: ExportAudience,
        version_id: UUID | None = None,
    ) -> ExportJob:
        await self.authorization.require_permission(
            tenant_id=self.context.tenant_id,
            user_id=self.context.user_id,
            permission_code="outputs.export",
        )
        output, lifecycle, current, current_safety = await GeneratedOutputService(
            self.session, self.context
        ).get(output_id)
        version = current
        if version_id and version_id != current.id:
            version = await self.session.scalar(
                select(OutputVersion).where(
                    OutputVersion.tenant_id == self.context.tenant_id,
                    OutputVersion.generated_output_id == output.id,
                    OutputVersion.id == version_id,
                )
            )
            if version is None:
                raise HTTPException(status_code=404, detail="Output version not found.")
        safety = await self.session.scalar(
            select(AssessmentSafetyReview).where(
                AssessmentSafetyReview.tenant_id == self.context.tenant_id,
                AssessmentSafetyReview.output_version_id == version.id,
            )
        )
        if safety is None:
            raise HTTPException(status_code=409, detail="This output version has no safety review.")
        if audience == ExportAudience.STUDENT_COPY:
            if lifecycle.review_required and lifecycle.workflow_status != OutputWorkflowStatus.RELEASED.value:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="A high-stakes student copy can be exported only after approval and release.",
                )
            if safety.blocked_reasons:
                raise HTTPException(status_code=409, detail="Blocked safety findings prevent student export.")
            sanitised = self.renderer.prepare_content(version.content_text, audience)
            sanitised_safety = self.safety_evaluator.evaluate(
                task_type=TeachingTaskType(output.output_type),
                content=sanitised,
                detected_total_marks=None,
                module_context_available=bool(lifecycle.module_offering_id),
            )
            if sanitised_safety.answers_detected or sanitised_safety.personal_data_detected:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="The sanitised student copy still contains confidential answer or personal data.",
                )

        job = ExportJob(
            id=uuid4(),
            tenant_id=self.context.tenant_id,
            generated_output_id=output.id,
            output_version_id=version.id,
            requested_by_user_id=self.context.user_id,
            export_format=export_format.value,
            audience=audience.value,
            status=ExportStatus.GENERATING.value,
            safety_review_id=safety.id,
            export_metadata={"renderer_version": "1.1", "student_copy_sanitised": audience == ExportAudience.STUDENT_COPY},
        )
        self.session.add(job)
        await self.session.flush()
        try:
            rendered = self.renderer.render(
                title=output.title,
                markdown=version.content_text,
                export_format=export_format,
                audience=audience,
            )
            filename = safe_export_filename(output.title, rendered.extension)
            object_key = (
                f"tenants/{self.context.tenant_id}/generated-outputs/{output.id}/"
                f"versions/{version.version_number}/exports/{job.id}/{filename}"
            )
            stored = await self.storage.put_bytes(
                tenant_id=self.context.tenant_id,
                object_key=object_key,
                content=rendered.content,
                media_type=rendered.media_type,
                metadata={
                    "generated-output-id": str(output.id),
                    "output-version-id": str(version.id),
                    "audience": audience.value,
                },
            )
            storage_row = StorageObject(
                id=uuid4(),
                tenant_id=self.context.tenant_id,
                provider="s3",
                bucket_name=stored.bucket_name,
                object_key=stored.object_key,
                storage_version_id=stored.storage_version_id,
                etag=stored.etag,
                sha256=stored.sha256,
                size_bytes=stored.size_bytes,
                media_type=stored.media_type,
            )
            self.session.add(storage_row)
            await self.session.flush()
            job.storage_object_id = storage_row.id
            job.filename = filename
            job.media_type = rendered.media_type
            job.size_bytes = len(rendered.content)
            job.status = ExportStatus.COMPLETED.value
            job.generated_at = datetime.now(timezone.utc)
            await self.audit.record(
                action="teaching_output.exported",
                resource_type="export_job",
                resource_id=job.id,
                metadata={
                    "generated_output_id": str(output.id),
                    "format": export_format.value,
                    "audience": audience.value,
                },
            )
        except Exception as exc:
            job.status = ExportStatus.FAILED.value
            job.error_code = "export_generation_failed"
            job.error_detail = str(exc)[:2000]
            raise
        await self.session.flush()
        return job

    async def require_download(self, export_id: UUID) -> tuple[ExportJob, StorageObject]:
        await self.authorization.require_permission(
            tenant_id=self.context.tenant_id,
            user_id=self.context.user_id,
            permission_code="outputs.export",
        )
        row = (
            await self.session.execute(
                select(ExportJob, StorageObject)
                .join(StorageObject, StorageObject.id == ExportJob.storage_object_id)
                .where(
                    ExportJob.tenant_id == self.context.tenant_id,
                    StorageObject.tenant_id == self.context.tenant_id,
                    ExportJob.id == export_id,
                    ExportJob.status == ExportStatus.COMPLETED.value,
                )
            )
        ).first()
        if row is None:
            raise HTTPException(status_code=404, detail="Completed export not found.")
        job, storage = row
        # Reuse output access checks to avoid download-by-identifier.
        await GeneratedOutputService(self.session, self.context).get(job.generated_output_id)
        return job, storage
