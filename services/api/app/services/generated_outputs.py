from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID, uuid4

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from services.database.models import (
    AssessmentSafetyReview,
    Conversation,
    GeneratedOutput,
    OutputLifecycle,
    OutputVersion,
    OutputWorkflowAction,
)
from services.database.models.enums import OutputWorkflowStatus

from ..ai.contracts import TeachingTaskType
from ..core.request_context import RequestContext
from .assessment_safety import AssessmentSafetyEvaluator
from .audit import AuditService
from .authorization import AuthorizationService
from .teaching_output_workflow import TeachingOutputWorkflow


class GeneratedOutputService:
    TRANSITIONS = {
        (OutputWorkflowStatus.DRAFT.value, "submit_for_review"): OutputWorkflowStatus.UNDER_REVIEW.value,
        (OutputWorkflowStatus.UNDER_REVIEW.value, "request_changes"): OutputWorkflowStatus.CHANGES_REQUESTED.value,
        (OutputWorkflowStatus.UNDER_REVIEW.value, "approve"): OutputWorkflowStatus.APPROVED.value,
        (OutputWorkflowStatus.UNDER_REVIEW.value, "reject"): OutputWorkflowStatus.REJECTED.value,
        (OutputWorkflowStatus.REJECTED.value, "return_to_draft"): OutputWorkflowStatus.DRAFT.value,
        (OutputWorkflowStatus.CHANGES_REQUESTED.value, "return_to_draft"): OutputWorkflowStatus.DRAFT.value,
        (OutputWorkflowStatus.APPROVED.value, "release"): OutputWorkflowStatus.RELEASED.value,
        (OutputWorkflowStatus.DRAFT.value, "archive"): OutputWorkflowStatus.ARCHIVED.value,
        (OutputWorkflowStatus.CHANGES_REQUESTED.value, "archive"): OutputWorkflowStatus.ARCHIVED.value,
        (OutputWorkflowStatus.APPROVED.value, "archive"): OutputWorkflowStatus.ARCHIVED.value,
        (OutputWorkflowStatus.RELEASED.value, "archive"): OutputWorkflowStatus.ARCHIVED.value,
    }

    def __init__(self, session: AsyncSession, context: RequestContext) -> None:
        self.session = session
        self.context = context
        self.authorization = AuthorizationService(session, context)
        self.audit = AuditService(session, context)
        self.safety = AssessmentSafetyEvaluator()
        self.workflow = TeachingOutputWorkflow()

    async def get(self, output_id: UUID):
        output, conversation, lifecycle = await self._owned_or_authorised(output_id)
        version = await self.session.scalar(
            select(OutputVersion).where(
                OutputVersion.tenant_id == self.context.tenant_id,
                OutputVersion.id == output.current_version_id,
            )
        )
        if version is None:
            raise HTTPException(status_code=404, detail="Current output version not found.")
        safety = await self._safety_for_version(output.id, version.id)
        return output, lifecycle, version, safety

    async def list_versions(self, output_id: UUID) -> list[OutputVersion]:
        await self._owned_or_authorised(output_id)
        return list(
            await self.session.scalars(
                select(OutputVersion)
                .where(
                    OutputVersion.tenant_id == self.context.tenant_id,
                    OutputVersion.generated_output_id == output_id,
                )
                .order_by(OutputVersion.version_number.desc())
            )
        )

    async def create_version(
        self, *, output_id: UUID, content_markdown: str, change_reason: str
    ) -> tuple[OutputVersion, AssessmentSafetyReview, OutputLifecycle]:
        output, conversation, lifecycle = await self._owned_or_authorised(output_id, require_owner=True)
        await self.authorization.require_permission(
            tenant_id=self.context.tenant_id,
            user_id=self.context.user_id,
            permission_code="outputs.edit",
        )
        if lifecycle.workflow_status in {
            OutputWorkflowStatus.APPROVED.value,
            OutputWorkflowStatus.RELEASED.value,
            OutputWorkflowStatus.ARCHIVED.value,
        }:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Approved, released, or archived outputs cannot be edited in place. Create a new draft from a previous version.",
            )
        current = await self.session.scalar(
            select(OutputVersion).where(OutputVersion.id == output.current_version_id)
        )
        next_number = int(
            await self.session.scalar(
                select(func.coalesce(func.max(OutputVersion.version_number), 0)).where(
                    OutputVersion.tenant_id == self.context.tenant_id,
                    OutputVersion.generated_output_id == output.id,
                )
            )
            or 0
        ) + 1
        task_type = TeachingTaskType(output.output_type)
        structured = self.workflow.structure(
            task_type=task_type,
            markdown=content_markdown,
            classification=(current.structured_content.get("classification", {}) if current else {}),
            module_context=(current.structured_content.get("module_context", {}) if current else {}),
        )
        version = OutputVersion(
            id=uuid4(),
            tenant_id=self.context.tenant_id,
            generated_output_id=output.id,
            version_number=next_number,
            previous_version_id=current.id if current else None,
            created_by_user_id=self.context.user_id,
            model_execution_id=None,
            content_text=content_markdown,
            structured_content=structured,
            change_reason=change_reason,
        )
        self.session.add(version)
        await self.session.flush()
        output.current_version_id = version.id
        if lifecycle.workflow_status in {
            OutputWorkflowStatus.CHANGES_REQUESTED.value,
            OutputWorkflowStatus.REJECTED.value,
        }:
            lifecycle.workflow_status = OutputWorkflowStatus.DRAFT.value
        review = await self._create_safety_review(output, lifecycle, version)
        await self.audit.record(
            action="teaching_output.version_created",
            resource_type="generated_output",
            resource_id=output.id,
            metadata={"version_number": next_number, "change_reason": change_reason},
        )
        return version, review, lifecycle

    async def restore_version(
        self, *, output_id: UUID, source_version_id: UUID, change_reason: str
    ) -> tuple[OutputVersion, AssessmentSafetyReview, OutputLifecycle]:
        source = await self.session.scalar(
            select(OutputVersion).where(
                OutputVersion.tenant_id == self.context.tenant_id,
                OutputVersion.generated_output_id == output_id,
                OutputVersion.id == source_version_id,
            )
        )
        if source is None:
            raise HTTPException(status_code=404, detail="Output version not found.")
        return await self.create_version(
            output_id=output_id,
            content_markdown=source.content_text,
            change_reason=f"{change_reason} (restored from version {source.version_number})",
        )

    async def transition(
        self, *, output_id: UUID, action: str, reason: str
    ) -> tuple[OutputLifecycle, OutputWorkflowAction]:
        output, conversation, lifecycle = await self._owned_or_authorised(output_id)
        permission = {
            "submit_for_review": "outputs.edit",
            "return_to_draft": "outputs.edit",
            "request_changes": "outputs.review",
            "approve": "outputs.approve",
            "reject": "outputs.approve",
            "release": "outputs.release",
            "archive": "outputs.edit",
        }[action]
        await self.authorization.require_permission(
            tenant_id=self.context.tenant_id,
            user_id=self.context.user_id,
            permission_code=permission,
            scope_type=("module_offering" if lifecycle.module_offering_id else None),
            scope_id=lifecycle.module_offering_id,
        )
        key = (lifecycle.workflow_status, action)
        new_status = self.TRANSITIONS.get(key)
        if new_status is None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Action '{action}' is not valid from status '{lifecycle.workflow_status}'.",
            )
        current_version = await self.session.scalar(
            select(OutputVersion).where(OutputVersion.id == output.current_version_id)
        )
        safety = await self._safety_for_version(output.id, current_version.id)
        if action in {"approve", "release"} and safety.blocked_reasons:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="The output has blocked assessment-safety findings and cannot be approved or released.",
            )
        if action == "release" and lifecycle.review_required and lifecycle.approved_at is None:
            raise HTTPException(status_code=409, detail="Human approval is required before release.")
        previous = lifecycle.workflow_status
        lifecycle.workflow_status = new_status
        now = datetime.now(timezone.utc)
        if action == "approve":
            lifecycle.approved_by_user_id = self.context.user_id
            lifecycle.approved_at = now
            output.is_formally_approved = True
        elif action == "release":
            lifecycle.released_by_user_id = self.context.user_id
            lifecycle.released_at = now
            lifecycle.student_release_allowed = safety.student_copy_safe or not safety.answers_detected
        elif action == "archive":
            lifecycle.archived_at = now
        elif action in {"request_changes", "return_to_draft", "reject"}:
            lifecycle.approved_by_user_id = None
            lifecycle.approved_at = None
            output.is_formally_approved = False

        workflow_action = OutputWorkflowAction(
            id=uuid4(),
            tenant_id=self.context.tenant_id,
            generated_output_id=output.id,
            output_version_id=current_version.id,
            action=action,
            previous_status=previous,
            new_status=new_status,
            performed_by_user_id=self.context.user_id,
            active_role_code=self.context.role_code,
            reason=reason,
            action_metadata={"permission": permission, "safety_status": safety.status},
        )
        self.session.add(workflow_action)
        await self.audit.record(
            action=f"teaching_output.{action}",
            resource_type="generated_output",
            resource_id=output.id,
            metadata={"from": previous, "to": new_status, "reason": reason},
        )
        await self.session.flush()
        return lifecycle, workflow_action

    async def history(self, output_id: UUID) -> list[OutputWorkflowAction]:
        await self._owned_or_authorised(output_id)
        return list(
            await self.session.scalars(
                select(OutputWorkflowAction)
                .where(
                    OutputWorkflowAction.tenant_id == self.context.tenant_id,
                    OutputWorkflowAction.generated_output_id == output_id,
                )
                .order_by(OutputWorkflowAction.created_at.desc())
            )
        )

    async def _owned_or_authorised(self, output_id: UUID, require_owner: bool = False):
        row = (
            await self.session.execute(
                select(GeneratedOutput, Conversation, OutputLifecycle)
                .join(Conversation, Conversation.id == GeneratedOutput.conversation_id)
                .join(OutputLifecycle, OutputLifecycle.generated_output_id == GeneratedOutput.id)
                .where(
                    GeneratedOutput.tenant_id == self.context.tenant_id,
                    Conversation.tenant_id == self.context.tenant_id,
                    OutputLifecycle.tenant_id == self.context.tenant_id,
                    GeneratedOutput.id == output_id,
                )
            )
        ).first()
        if row is None:
            raise HTTPException(status_code=404, detail="Teaching output not found.")
        output, conversation, lifecycle = row
        is_owner = conversation.owner_user_id == self.context.user_id
        if require_owner and not is_owner:
            raise HTTPException(status_code=403, detail="Only the output owner can edit this draft.")
        if not is_owner:
            await self.authorization.require_permission(
                tenant_id=self.context.tenant_id,
                user_id=self.context.user_id,
                permission_code="outputs.review",
                scope_type=("module_offering" if lifecycle.module_offering_id else None),
                scope_id=lifecycle.module_offering_id,
            )
        return output, conversation, lifecycle

    async def _safety_for_version(self, output_id: UUID, version_id: UUID) -> AssessmentSafetyReview:
        review = await self.session.scalar(
            select(AssessmentSafetyReview).where(
                AssessmentSafetyReview.tenant_id == self.context.tenant_id,
                AssessmentSafetyReview.generated_output_id == output_id,
                AssessmentSafetyReview.output_version_id == version_id,
            )
        )
        if review is None:
            raise HTTPException(status_code=404, detail="Assessment safety review not found.")
        return review

    async def _create_safety_review(
        self, output: GeneratedOutput, lifecycle: OutputLifecycle, version: OutputVersion
    ) -> AssessmentSafetyReview:
        task_type = TeachingTaskType(output.output_type)
        detected_marks = version.structured_content.get("classification", {}).get("detected_entities", {}).get("total_marks")
        evaluation = self.safety.evaluate(
            task_type=task_type,
            content=version.content_text,
            detected_total_marks=int(detected_marks) if detected_marks is not None else None,
            module_context_available=bool(lifecycle.module_offering_id),
        )
        review = AssessmentSafetyReview(
            id=uuid4(),
            tenant_id=self.context.tenant_id,
            generated_output_id=output.id,
            output_version_id=version.id,
            status=evaluation.status.value,
            risk_level=evaluation.risk_level.value,
            checks=evaluation.checks,
            warnings=evaluation.warnings,
            blocked_reasons=evaluation.blocked_reasons,
            answers_detected=evaluation.answers_detected,
            personal_data_detected=evaluation.personal_data_detected,
            student_copy_safe=evaluation.student_copy_safe,
        )
        self.session.add(review)
        lifecycle.risk_level = evaluation.risk_level.value
        lifecycle.answer_key_present = evaluation.answers_detected
        lifecycle.student_release_allowed = evaluation.student_copy_safe
        await self.session.flush()
        return review
