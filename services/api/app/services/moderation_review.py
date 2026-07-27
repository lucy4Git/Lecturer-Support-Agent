from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from services.database.models import (
    AssignedReviewTask,
    Conversation,
    ExternalAccessGrant,
    ExportJob,
    GeneratedOutput,
    OutputLifecycle,
    OutputVersion,
    Membership,
    Role,
    RoleAssignment,
    ReviewCorrectionRound,
    ReviewCycle,
    ReviewDecision,
    ReviewFinding,
    ReviewFindingResponse,
    ReviewPack,
    ReviewPackItem,
    ReviewSubmission,
)
from services.database.models.enums import (
    OutputWorkflowStatus,
    ReviewCorrectionStatus,
    ReviewCycleStatus,
    ReviewDecisionCode,
    ReviewFindingStatus,
    ReviewTaskStatus,
)

from ..core.request_context import RequestContext
from .audit import AuditService
from .authorization import AuthorizationService
from .generated_outputs import GeneratedOutputService
from .document_access import DocumentAccessService
from .notifications import NotificationService


EXTERNAL_ROLES = {"external_moderator", "external_reviewer"}


class ReviewStateMachine:
    TASK_TRANSITIONS = {
        (ReviewTaskStatus.ASSIGNED.value, "accept"): ReviewTaskStatus.ACCEPTED.value,
        (ReviewTaskStatus.ACCEPTED.value, "start"): ReviewTaskStatus.IN_PROGRESS.value,
        (ReviewTaskStatus.IN_PROGRESS.value, "submit"): ReviewTaskStatus.SUBMITTED.value,
        (ReviewTaskStatus.SUBMITTED.value, "complete"): ReviewTaskStatus.COMPLETED.value,
        (ReviewTaskStatus.RETURNED.value, "accept"): ReviewTaskStatus.ACCEPTED.value,
    }

    @classmethod
    def task_transition(cls, current: str, action: str) -> str:
        next_status = cls.TASK_TRANSITIONS.get((current, action))
        if next_status is None:
            raise ValueError(f"Action '{action}' is not valid from task status '{current}'.")
        return next_status

    @staticmethod
    def output_action_for_decision(decision: str) -> str:
        return {
            ReviewDecisionCode.APPROVED.value: "approve",
            ReviewDecisionCode.APPROVED_WITH_CONDITIONS.value: "request_changes",
            ReviewDecisionCode.CHANGES_REQUIRED.value: "request_changes",
            ReviewDecisionCode.REJECTED.value: "reject",
        }[decision]

    @staticmethod
    def cycle_status_for_decision(decision: str) -> str:
        return {
            ReviewDecisionCode.APPROVED.value: ReviewCycleStatus.APPROVED.value,
            ReviewDecisionCode.APPROVED_WITH_CONDITIONS.value: ReviewCycleStatus.CONDITIONALLY_APPROVED.value,
            ReviewDecisionCode.CHANGES_REQUIRED.value: ReviewCycleStatus.CHANGES_REQUESTED.value,
            ReviewDecisionCode.REJECTED.value: ReviewCycleStatus.REJECTED.value,
        }[decision]


@dataclass(frozen=True, slots=True)
class ReviewAssignee:
    user_id: UUID
    reviewer_role_code: str
    external_access_grant_id: UUID | None = None


class ExternalReviewScope:
    """Pure matcher used by service checks and tests.

    The grant is fail-closed: it must contain the requested action and at least
    one exact resource boundary that matches the assigned review task.
    """

    @staticmethod
    def permits(
        *,
        allowed_actions: list[str],
        resource_scope: dict[str, Any],
        action: str,
        identifiers: dict[str, UUID | None],
    ) -> bool:
        umbrella_actions = {
            "review.task.read",
            "review.task.accept",
            "review.task.start",
            "review.finding.create",
            "review.finding.update",
            "review.submit",
        }
        action_allowed = (
            action in allowed_actions
            or "review.*" in allowed_actions
            or ("review.task.perform" in allowed_actions and action in umbrella_actions)
        )
        if not action_allowed:
            return False
        matched_boundary = False
        for key, value in identifiers.items():
            if value is None or key not in resource_scope:
                continue
            expected = resource_scope[key]
            if isinstance(expected, list):
                if str(value) not in {str(item) for item in expected}:
                    return False
            elif str(expected) != str(value):
                return False
            matched_boundary = True
        return matched_boundary


class ModerationReviewService:
    def __init__(self, session: AsyncSession, context: RequestContext) -> None:
        self.session = session
        self.context = context
        self.authorization = AuthorizationService(session, context)
        self.audit = AuditService(session, context)
        self.outputs = GeneratedOutputService(session, context)
        self.notifications = NotificationService(session, context)

    async def create_cycle(
        self,
        *,
        generated_output_id: UUID,
        review_kind: str,
        due_at: datetime | None,
        instructions: str,
        criteria: list[str],
        assignees: list[ReviewAssignee],
        supporting_document_version_ids: list[UUID],
        supporting_export_ids: list[UUID],
    ) -> ReviewCycle:
        output, lifecycle, version, _ = await self.outputs.get(generated_output_id)
        await self.authorization.require_permission(
            tenant_id=self.context.tenant_id,
            user_id=self.context.user_id,
            permission_code="review_cycles.manage",
            scope_type="module_offering" if lifecycle.module_offering_id else None,
            scope_id=lifecycle.module_offering_id,
        )
        await self.authorization.require_permission(
            tenant_id=self.context.tenant_id,
            user_id=self.context.user_id,
            permission_code="review_tasks.assign",
            scope_type="module_offering" if lifecycle.module_offering_id else None,
            scope_id=lifecycle.module_offering_id,
        )
        if due_at is not None and due_at <= datetime.now(timezone.utc):
            raise HTTPException(status_code=422, detail="Review due date must be in the future.")
        if lifecycle.workflow_status != OutputWorkflowStatus.UNDER_REVIEW.value:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="The output must be submitted for review before a moderation cycle is assigned.",
            )
        if len({item.user_id for item in assignees}) != len(assignees):
            raise HTTPException(status_code=422, detail="Each reviewer may be assigned only once per round.")
        for assignee in assignees:
            await self._require_reviewer_role(assignee.user_id, assignee.reviewer_role_code)
        for version_id in supporting_document_version_ids:
            await DocumentAccessService(self.session, self.context).require_version(version_id)
        if supporting_export_ids:
            valid_exports = set(
                await self.session.scalars(
                    select(ExportJob.id).where(
                        ExportJob.tenant_id == self.context.tenant_id,
                        ExportJob.id.in_(supporting_export_ids),
                        ExportJob.generated_output_id == generated_output_id,
                    )
                )
            )
            missing_exports = set(supporting_export_ids) - valid_exports
            if missing_exports:
                raise HTTPException(status_code=404, detail="One or more supporting exports are unavailable for this output.")
        cycle_number = int(
            await self.session.scalar(
                select(func.coalesce(func.max(ReviewCycle.cycle_number), 0)).where(
                    ReviewCycle.tenant_id == self.context.tenant_id,
                    ReviewCycle.generated_output_id == generated_output_id,
                )
            )
            or 0
        ) + 1
        now = datetime.now(timezone.utc)
        cycle = ReviewCycle(
            id=uuid4(),
            tenant_id=self.context.tenant_id,
            generated_output_id=generated_output_id,
            initiating_output_version_id=version.id,
            module_offering_id=lifecycle.module_offering_id,
            initiated_by_user_id=self.context.user_id,
            review_kind=review_kind,
            cycle_number=cycle_number,
            current_round=1,
            status=ReviewCycleStatus.ASSIGNED.value,
            due_at=due_at,
            criteria_snapshot=[{"code": f"C{index + 1}", "statement": value} for index, value in enumerate(criteria)],
            policy_snapshot={
                "assignment_specific_access": True,
                "exact_output_version": str(version.id),
                "reviewer_recommendation_is_not_formal_approval": True,
            },
        )
        self.session.add(cycle)
        await self.session.flush()
        pack = await self._create_pack(
            cycle=cycle,
            output=output,
            version=version,
            supporting_document_version_ids=supporting_document_version_ids,
            supporting_export_ids=supporting_export_ids,
        )
        for assignee in assignees:
            if assignee.reviewer_role_code in EXTERNAL_ROLES:
                await self._require_external_grant(
                    grant_id=assignee.external_access_grant_id,
                    user_id=assignee.user_id,
                    action="review.task.perform",
                    identifiers={
                        "generated_output_id": output.id,
                        "output_version_id": version.id,
                        "review_cycle_id": cycle.id,
                        "module_offering_id": lifecycle.module_offering_id,
                    },
                )
            task = AssignedReviewTask(
                id=uuid4(),
                tenant_id=self.context.tenant_id,
                assigned_user_id=assignee.user_id,
                assigned_by_user_id=self.context.user_id,
                external_access_grant_id=assignee.external_access_grant_id,
                review_cycle_id=cycle.id,
                review_pack_id=pack.id,
                reviewer_role_code=assignee.reviewer_role_code,
                review_kind=review_kind,
                round_number=1,
                task_type=review_kind,
                target_type="output_version",
                target_id=version.id,
                status=ReviewTaskStatus.ASSIGNED.value,
                due_at=due_at,
                instructions=instructions,
                permissions_snapshot={
                    "allowed": ["review.task.read", "review.task.accept", "review.finding.create", "review.submit"],
                    "criteria": cycle.criteria_snapshot,
                    "output_version_id": str(version.id),
                },
                task_metadata={"cycle_number": cycle_number},
            )
            self.session.add(task)
            await self.notifications.emit(
                recipient_user_id=assignee.user_id,
                notification_type="review_task_assigned",
                title="New review task assigned",
                body=f"A {review_kind.replace('_', ' ')} task has been assigned to you for review round 1.",
                severity="information",
                action_path="action:reviewTasks",
                resource_type="assigned_review_task",
                resource_id=task.id,
                expires_at=due_at,
                metadata={"review_cycle_id": str(cycle.id), "output_version_id": str(version.id)},
            )
        await self.audit.record(
            action="review_cycle.created",
            resource_type="review_cycle",
            resource_id=cycle.id,
            metadata={
                "generated_output_id": str(generated_output_id),
                "output_version_id": str(version.id),
                "review_kind": review_kind,
                "reviewers": [str(item.user_id) for item in assignees],
            },
        )
        await self.session.flush()
        return cycle

    async def get_cycle(self, cycle_id: UUID) -> tuple[ReviewCycle, list[AssignedReviewTask], list[ReviewPackItem], int, int]:
        cycle = await self._cycle(cycle_id)
        await self._require_cycle_visibility(cycle)
        tasks = list(
            await self.session.scalars(
                select(AssignedReviewTask).where(
                    AssignedReviewTask.tenant_id == self.context.tenant_id,
                    AssignedReviewTask.review_cycle_id == cycle.id,
                ).order_by(AssignedReviewTask.round_number, AssignedReviewTask.created_at)
            )
        )
        current_pack_ids = [task.review_pack_id for task in tasks if task.round_number == cycle.current_round and task.review_pack_id]
        items: list[ReviewPackItem] = []
        if current_pack_ids:
            items = list(
                await self.session.scalars(
                    select(ReviewPackItem).where(
                        ReviewPackItem.tenant_id == self.context.tenant_id,
                        ReviewPackItem.review_pack_id.in_(current_pack_ids),
                    )
                )
            )
        open_findings = int(
            await self.session.scalar(
                select(func.count(ReviewFinding.id)).where(
                    ReviewFinding.tenant_id == self.context.tenant_id,
                    ReviewFinding.review_cycle_id == cycle.id,
                    ReviewFinding.status.in_([
                        ReviewFindingStatus.OPEN.value,
                        ReviewFindingStatus.RESPONDED.value,
                        ReviewFindingStatus.DISPUTED.value,
                    ]),
                )
            )
            or 0
        )
        blocking_findings = int(
            await self.session.scalar(
                select(func.count(ReviewFinding.id)).where(
                    ReviewFinding.tenant_id == self.context.tenant_id,
                    ReviewFinding.review_cycle_id == cycle.id,
                    ReviewFinding.is_blocking.is_(True),
                    ReviewFinding.status.notin_([
                        ReviewFindingStatus.RESOLVED.value,
                        ReviewFindingStatus.WITHDRAWN.value,
                    ]),
                )
            )
            or 0
        )
        return cycle, tasks, items, open_findings, blocking_findings

    async def list_findings(self, cycle_id: UUID) -> list[ReviewFinding]:
        cycle = await self._cycle(cycle_id)
        await self._require_cycle_visibility(cycle)
        return list(
            await self.session.scalars(
                select(ReviewFinding).where(
                    ReviewFinding.tenant_id == self.context.tenant_id,
                    ReviewFinding.review_cycle_id == cycle.id,
                ).order_by(ReviewFinding.created_at)
            )
        )

    async def list_my_tasks(self, task_status: str | None = None, limit: int = 100) -> list[AssignedReviewTask]:
        statement = select(AssignedReviewTask).where(
            AssignedReviewTask.tenant_id == self.context.tenant_id,
            AssignedReviewTask.assigned_user_id == self.context.user_id,
        )
        if task_status:
            statement = statement.where(AssignedReviewTask.status == task_status)
        return list(await self.session.scalars(statement.order_by(AssignedReviewTask.created_at.desc()).limit(limit)))

    async def get_task(self, task_id: UUID) -> AssignedReviewTask:
        task = await self._task(task_id)
        await self._require_task_access(task, "review.task.read")
        return task

    async def task_action(self, task_id: UUID, action: str, reason: str) -> AssignedReviewTask:
        task = await self._task(task_id, lock=True)
        await self._require_task_access(task, f"review.task.{action}")
        try:
            next_status = ReviewStateMachine.task_transition(task.status, action)
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        now = datetime.now(timezone.utc)
        task.status = next_status
        if action == "accept":
            task.accepted_at = now
        elif action == "start":
            task.started_at = now
            cycle = await self._cycle(task.review_cycle_id)
            if cycle.status == ReviewCycleStatus.ASSIGNED.value:
                cycle.status = ReviewCycleStatus.IN_REVIEW.value
                cycle.started_at = cycle.started_at or now
        await self.audit.record(
            action=f"review_task.{action}",
            resource_type="assigned_review_task",
            resource_id=task.id,
            metadata={"reason": reason, "new_status": next_status},
        )
        await self.session.flush()
        return task

    async def create_finding(self, task_id: UUID, payload: dict[str, Any]) -> ReviewFinding:
        task = await self._task(task_id)
        await self._require_task_access(task, "review.finding.create")
        if task.status == ReviewTaskStatus.ACCEPTED.value:
            await self.task_action(task.id, "start", "Finding creation started the assigned review task.")
        elif task.status != ReviewTaskStatus.IN_PROGRESS.value:
            raise HTTPException(status_code=409, detail="Findings can only be added while a task is in progress.")
        finding = ReviewFinding(
            id=uuid4(),
            tenant_id=self.context.tenant_id,
            review_cycle_id=task.review_cycle_id,
            review_task_id=task.id,
            source_output_version_id=task.target_id,
            created_by_user_id=self.context.user_id,
            criterion_code=payload.get("criterion_code"),
            category=payload["category"],
            severity=payload["severity"],
            title=payload["title"],
            description=payload["description"],
            evidence_locator=payload.get("evidence_locator"),
            recommendation=payload.get("recommendation"),
            is_blocking=bool(payload.get("is_blocking")),
            status=ReviewFindingStatus.OPEN.value,
            finding_metadata=payload.get("metadata") or {},
        )
        self.session.add(finding)
        await self.audit.record(
            action="review_finding.created",
            resource_type="review_finding",
            resource_id=finding.id,
            metadata={"review_task_id": str(task.id), "severity": finding.severity, "blocking": finding.is_blocking},
        )
        await self.session.flush()
        return finding

    async def update_finding(self, finding_id: UUID, changes: dict[str, Any]) -> ReviewFinding:
        finding, task = await self._finding_with_task(finding_id)
        await self._require_task_access(task, "review.finding.update")
        if finding.created_by_user_id != self.context.user_id:
            raise HTTPException(status_code=403, detail="Only the assigned reviewer who created the finding can edit it.")
        if task.status == ReviewTaskStatus.SUBMITTED.value:
            raise HTTPException(status_code=409, detail="Submitted review findings are immutable.")
        for field in (
            "severity", "title", "description", "evidence_locator", "recommendation", "is_blocking", "status"
        ):
            if field in changes and changes[field] is not None:
                setattr(finding, field, changes[field])
        await self.audit.record(
            action="review_finding.updated",
            resource_type="review_finding",
            resource_id=finding.id,
            metadata={"fields": sorted(k for k, v in changes.items() if v is not None)},
        )
        await self.session.flush()
        return finding

    async def respond_to_finding(
        self,
        finding_id: UUID,
        *,
        response_type: str,
        body: str,
        related_output_version_id: UUID | None,
        metadata: dict[str, Any],
    ) -> ReviewFindingResponse:
        finding, task = await self._finding_with_task(finding_id)
        cycle = await self._cycle(finding.review_cycle_id)
        output, conversation, lifecycle = await self._output_row(cycle.generated_output_id)
        is_owner = conversation.owner_user_id == self.context.user_id
        if not is_owner:
            await self.authorization.require_permission(
                tenant_id=self.context.tenant_id,
                user_id=self.context.user_id,
                permission_code="review_findings.respond",
                scope_type="module_offering" if lifecycle.module_offering_id else None,
                scope_id=lifecycle.module_offering_id,
            )
        response = ReviewFindingResponse(
            id=uuid4(),
            tenant_id=self.context.tenant_id,
            review_finding_id=finding.id,
            responded_by_user_id=self.context.user_id,
            response_type=response_type,
            body=body,
            related_output_version_id=related_output_version_id,
            response_metadata=metadata,
        )
        self.session.add(response)
        finding.status = (
            ReviewFindingStatus.DISPUTED.value
            if response_type == "dispute"
            else ReviewFindingStatus.RESPONDED.value
        )
        await self.audit.record(
            action="review_finding.responded",
            resource_type="review_finding",
            resource_id=finding.id,
            metadata={"response_type": response_type},
        )
        await self.session.flush()
        return response

    async def submit_review(
        self,
        task_id: UUID,
        *,
        recommendation: str,
        summary: str,
        criterion_assessments: list[dict[str, Any]],
        declaration_accepted: bool,
    ) -> ReviewSubmission:
        task = await self._task(task_id, lock=True)
        await self._require_task_access(task, "review.submit")
        if not declaration_accepted:
            raise HTTPException(status_code=422, detail="Reviewer declaration is required.")
        if task.status == ReviewTaskStatus.ACCEPTED.value:
            await self.task_action(task.id, "start", "Review submission started the task.")
        elif task.status != ReviewTaskStatus.IN_PROGRESS.value:
            raise HTTPException(status_code=409, detail="Only an in-progress review task can be submitted.")
        number = int(
            await self.session.scalar(
                select(func.coalesce(func.max(ReviewSubmission.submission_number), 0)).where(
                    ReviewSubmission.tenant_id == self.context.tenant_id,
                    ReviewSubmission.review_task_id == task.id,
                )
            )
            or 0
        ) + 1
        now = datetime.now(timezone.utc)
        canonical = json.dumps(
            {
                "task_id": str(task.id),
                "round": task.round_number,
                "recommendation": recommendation,
                "summary": summary,
                "criterion_assessments": criterion_assessments,
                "reviewer": str(self.context.user_id),
            },
            sort_keys=True,
            separators=(",", ":"),
        )
        submission = ReviewSubmission(
            id=uuid4(),
            tenant_id=self.context.tenant_id,
            review_cycle_id=task.review_cycle_id,
            review_task_id=task.id,
            reviewer_user_id=self.context.user_id,
            round_number=task.round_number,
            submission_number=number,
            recommendation=recommendation,
            summary=summary,
            criterion_assessments=criterion_assessments,
            declaration_accepted=True,
            immutable_sha256=hashlib.sha256(canonical.encode()).hexdigest(),
            submitted_at=now,
        )
        self.session.add(submission)
        task.status = ReviewTaskStatus.SUBMITTED.value
        task.submitted_at = now
        cycle = await self._cycle(task.review_cycle_id)
        pending = int(
            await self.session.scalar(
                select(func.count(AssignedReviewTask.id)).where(
                    AssignedReviewTask.tenant_id == self.context.tenant_id,
                    AssignedReviewTask.review_cycle_id == cycle.id,
                    AssignedReviewTask.round_number == cycle.current_round,
                    AssignedReviewTask.status != ReviewTaskStatus.SUBMITTED.value,
                    AssignedReviewTask.id != task.id,
                )
            )
            or 0
        )
        if pending == 0:
            cycle.status = ReviewCycleStatus.DECISION_PENDING.value
        await self.audit.record(
            action="review_submission.created",
            resource_type="review_submission",
            resource_id=submission.id,
            metadata={"task_id": str(task.id), "recommendation": recommendation, "sha256": submission.immutable_sha256},
        )
        await self.session.flush()
        return submission

    async def record_decision(
        self,
        cycle_id: UUID,
        *,
        decision: str,
        reason: str,
        conditions: list[str],
        correction_due_at: datetime | None,
    ) -> ReviewDecision:
        cycle = await self._cycle(cycle_id, lock=True)
        await self.authorization.require_permission(
            tenant_id=self.context.tenant_id,
            user_id=self.context.user_id,
            permission_code="review_decisions.record",
            scope_type="module_offering" if cycle.module_offering_id else None,
            scope_id=cycle.module_offering_id,
        )
        if cycle.status != ReviewCycleStatus.DECISION_PENDING.value:
            raise HTTPException(status_code=409, detail="A decision can only be recorded after all assigned reviews are submitted.")
        submissions = list(
            await self.session.scalars(
                select(ReviewSubmission).where(
                    ReviewSubmission.tenant_id == self.context.tenant_id,
                    ReviewSubmission.review_cycle_id == cycle.id,
                    ReviewSubmission.round_number == cycle.current_round,
                )
            )
        )
        if not submissions:
            raise HTTPException(status_code=409, detail="The review cycle has no submitted reviewer evidence.")
        now = datetime.now(timezone.utc)
        row = ReviewDecision(
            id=uuid4(),
            tenant_id=self.context.tenant_id,
            review_cycle_id=cycle.id,
            round_number=cycle.current_round,
            decided_by_user_id=self.context.user_id,
            decision=decision,
            reason=reason,
            conditions=conditions,
            linked_submission_ids=[str(item.id) for item in submissions],
            decided_at=now,
        )
        self.session.add(row)
        output_action = ReviewStateMachine.output_action_for_decision(decision)
        await self.outputs.transition(
            output_id=cycle.generated_output_id,
            action=output_action,
            reason=f"Review cycle {cycle.cycle_number}, round {cycle.current_round}: {reason}",
        )
        cycle.status = ReviewStateMachine.cycle_status_for_decision(decision)
        if decision == ReviewDecisionCode.APPROVED.value:
            cycle.completed_at = now
            cycle.closed_at = now
            for task in await self._current_round_tasks(cycle):
                task.status = ReviewTaskStatus.COMPLETED.value
                task.completed_at = now
        elif decision in {
            ReviewDecisionCode.APPROVED_WITH_CONDITIONS.value,
            ReviewDecisionCode.CHANGES_REQUIRED.value,
        }:
            version_id = await self.session.scalar(
                select(GeneratedOutput.current_version_id).where(GeneratedOutput.id == cycle.generated_output_id)
            )
            findings = list(
                await self.session.scalars(
                    select(ReviewFinding.id).where(
                        ReviewFinding.tenant_id == self.context.tenant_id,
                        ReviewFinding.review_cycle_id == cycle.id,
                        ReviewFinding.status.notin_([
                            ReviewFindingStatus.RESOLVED.value,
                            ReviewFindingStatus.WITHDRAWN.value,
                        ]),
                    )
                )
            )
            correction = ReviewCorrectionRound(
                id=uuid4(),
                tenant_id=self.context.tenant_id,
                review_cycle_id=cycle.id,
                round_number=cycle.current_round,
                requested_by_user_id=self.context.user_id,
                source_output_version_id=version_id,
                corrected_output_version_id=None,
                status=ReviewCorrectionStatus.REQUESTED.value,
                due_at=correction_due_at,
                requested_at=now,
                resolution_summary=None,
                finding_ids=[str(item) for item in findings],
            )
            self.session.add(correction)
        elif decision == ReviewDecisionCode.REJECTED.value:
            cycle.closed_at = now
        await self.audit.record(
            action="review_decision.recorded",
            resource_type="review_decision",
            resource_id=row.id,
            metadata={"cycle_id": str(cycle.id), "decision": decision, "round": cycle.current_round},
        )
        await self.session.flush()
        return row

    async def resubmit_correction(
        self,
        cycle_id: UUID,
        *,
        corrected_output_version_id: UUID,
        resolution_summary: str,
    ) -> ReviewCycle:
        cycle = await self._cycle(cycle_id, lock=True)
        if cycle.status not in {
            ReviewCycleStatus.CHANGES_REQUESTED.value,
            ReviewCycleStatus.CONDITIONALLY_APPROVED.value,
        }:
            raise HTTPException(status_code=409, detail="This review cycle is not awaiting corrections.")
        output, conversation, lifecycle = await self._output_row(cycle.generated_output_id)
        if conversation.owner_user_id != self.context.user_id:
            await self.authorization.require_permission(
                tenant_id=self.context.tenant_id,
                user_id=self.context.user_id,
                permission_code="review_findings.respond",
                scope_type="module_offering" if lifecycle.module_offering_id else None,
                scope_id=lifecycle.module_offering_id,
            )
        version = await self.session.scalar(
            select(OutputVersion).where(
                OutputVersion.tenant_id == self.context.tenant_id,
                OutputVersion.generated_output_id == cycle.generated_output_id,
                OutputVersion.id == corrected_output_version_id,
            )
        )
        if version is None or output.current_version_id != version.id:
            raise HTTPException(status_code=422, detail="Corrections must target the current immutable output version.")
        correction = await self.session.scalar(
            select(ReviewCorrectionRound).where(
                ReviewCorrectionRound.tenant_id == self.context.tenant_id,
                ReviewCorrectionRound.review_cycle_id == cycle.id,
                ReviewCorrectionRound.round_number == cycle.current_round,
            ).with_for_update()
        )
        if correction is None:
            raise HTTPException(status_code=404, detail="Correction round not found.")
        blocking_without_response = int(
            await self.session.scalar(
                select(func.count(ReviewFinding.id))
                .where(
                    ReviewFinding.tenant_id == self.context.tenant_id,
                    ReviewFinding.review_cycle_id == cycle.id,
                    ReviewFinding.is_blocking.is_(True),
                    ReviewFinding.status == ReviewFindingStatus.OPEN.value,
                )
            )
            or 0
        )
        if blocking_without_response:
            raise HTTPException(status_code=409, detail="Every blocking finding must receive a response before resubmission.")
        if lifecycle.workflow_status != OutputWorkflowStatus.DRAFT.value:
            raise HTTPException(status_code=409, detail="The corrected output must be a draft before resubmission.")
        await self.outputs.transition(
            output_id=cycle.generated_output_id,
            action="submit_for_review",
            reason=f"Correction round resubmitted: {resolution_summary}",
        )
        prior_tasks = await self._current_round_tasks(cycle)
        cycle.current_round += 1
        cycle.status = ReviewCycleStatus.ASSIGNED.value
        correction.corrected_output_version_id = version.id
        correction.status = ReviewCorrectionStatus.RESUBMITTED.value
        correction.resubmitted_at = datetime.now(timezone.utc)
        correction.resolution_summary = resolution_summary
        pack = await self._create_pack(
            cycle=cycle,
            output=output,
            version=version,
            supporting_document_version_ids=[],
            supporting_export_ids=[],
        )
        for prior in prior_tasks:
            task = AssignedReviewTask(
                id=uuid4(),
                    tenant_id=self.context.tenant_id,
                    assigned_user_id=prior.assigned_user_id,
                    assigned_by_user_id=self.context.user_id,
                    external_access_grant_id=prior.external_access_grant_id,
                    review_cycle_id=cycle.id,
                    review_pack_id=pack.id,
                    reviewer_role_code=prior.reviewer_role_code,
                    review_kind=prior.review_kind,
                    round_number=cycle.current_round,
                    task_type=prior.task_type,
                    target_type="output_version",
                    target_id=version.id,
                    status=ReviewTaskStatus.ASSIGNED.value,
                    due_at=cycle.due_at,
                    instructions=f"Correction round {cycle.current_round}. Review responses and the revised output.",
                    permissions_snapshot={**prior.permissions_snapshot, "output_version_id": str(version.id)},
                task_metadata={"resubmission_of_task_id": str(prior.id)},
            )
            self.session.add(task)
            await self.notifications.emit(
                recipient_user_id=prior.assigned_user_id,
                notification_type="review_correction_resubmitted",
                title="Corrected output ready for review",
                body=f"Correction round {cycle.current_round} is ready. Review the new sealed output version and earlier finding responses.",
                action_path="action:reviewTasks",
                resource_type="assigned_review_task",
                resource_id=task.id,
                expires_at=cycle.due_at,
                metadata={"review_cycle_id": str(cycle.id), "output_version_id": str(version.id)},
            )
        await self.audit.record(
            action="review_cycle.corrections_resubmitted",
            resource_type="review_cycle",
            resource_id=cycle.id,
            metadata={"round": cycle.current_round, "output_version_id": str(version.id)},
        )
        await self.session.flush()
        return cycle

    async def department_dashboard(self, organisational_unit_id: UUID) -> dict[str, int | UUID]:
        await self.authorization.require_permission(
            tenant_id=self.context.tenant_id,
            user_id=self.context.user_id,
            permission_code="review_dashboard.read",
            scope_type="organisational_unit",
            scope_id=organisational_unit_id,
        )
        from services.database.models import ModuleOffering

        now = datetime.now(timezone.utc)
        base = (
            select(ReviewCycle.id)
            .join(ModuleOffering, ModuleOffering.id == ReviewCycle.module_offering_id)
            .where(
                ReviewCycle.tenant_id == self.context.tenant_id,
                ModuleOffering.tenant_id == self.context.tenant_id,
                ModuleOffering.org_unit_id == organisational_unit_id,
            )
        )
        cycle_ids = list(await self.session.scalars(base))
        if not cycle_ids:
            return {
                "organisational_unit_id": organisational_unit_id,
                "active_cycles": 0,
                "decision_pending_cycles": 0,
                "overdue_cycles": 0,
                "assigned_tasks": 0,
                "in_progress_tasks": 0,
                "submitted_tasks": 0,
                "open_findings": 0,
                "blocking_findings": 0,
            }

        async def count_cycle(*conditions: Any) -> int:
            return int(await self.session.scalar(select(func.count(ReviewCycle.id)).where(
                ReviewCycle.tenant_id == self.context.tenant_id,
                ReviewCycle.id.in_(cycle_ids),
                *conditions,
            )) or 0)

        async def count_task(status_value: str) -> int:
            return int(await self.session.scalar(select(func.count(AssignedReviewTask.id)).where(
                AssignedReviewTask.tenant_id == self.context.tenant_id,
                AssignedReviewTask.review_cycle_id.in_(cycle_ids),
                AssignedReviewTask.status == status_value,
            )) or 0)

        open_statuses = [
            ReviewCycleStatus.ASSIGNED.value,
            ReviewCycleStatus.IN_REVIEW.value,
            ReviewCycleStatus.DECISION_PENDING.value,
            ReviewCycleStatus.CHANGES_REQUESTED.value,
            ReviewCycleStatus.CONDITIONALLY_APPROVED.value,
        ]
        return {
            "organisational_unit_id": organisational_unit_id,
            "active_cycles": await count_cycle(ReviewCycle.status.in_(open_statuses)),
            "decision_pending_cycles": await count_cycle(ReviewCycle.status == ReviewCycleStatus.DECISION_PENDING.value),
            "overdue_cycles": await count_cycle(ReviewCycle.due_at.is_not(None), ReviewCycle.due_at < now, ReviewCycle.status.in_(open_statuses)),
            "assigned_tasks": await count_task(ReviewTaskStatus.ASSIGNED.value),
            "in_progress_tasks": await count_task(ReviewTaskStatus.IN_PROGRESS.value),
            "submitted_tasks": await count_task(ReviewTaskStatus.SUBMITTED.value),
            "open_findings": int(await self.session.scalar(select(func.count(ReviewFinding.id)).where(
                ReviewFinding.tenant_id == self.context.tenant_id,
                ReviewFinding.review_cycle_id.in_(cycle_ids),
                ReviewFinding.status.in_([ReviewFindingStatus.OPEN.value, ReviewFindingStatus.RESPONDED.value, ReviewFindingStatus.DISPUTED.value]),
            )) or 0),
            "blocking_findings": int(await self.session.scalar(select(func.count(ReviewFinding.id)).where(
                ReviewFinding.tenant_id == self.context.tenant_id,
                ReviewFinding.review_cycle_id.in_(cycle_ids),
                ReviewFinding.is_blocking.is_(True),
                ReviewFinding.status.notin_([ReviewFindingStatus.RESOLVED.value, ReviewFindingStatus.WITHDRAWN.value]),
            )) or 0),
        }

    async def _create_pack(
        self,
        *,
        cycle: ReviewCycle,
        output: GeneratedOutput,
        version: OutputVersion,
        supporting_document_version_ids: list[UUID],
        supporting_export_ids: list[UUID],
    ) -> ReviewPack:
        now = datetime.now(timezone.utc)
        manifest = {
            "review_cycle_id": str(cycle.id),
            "round_number": cycle.current_round,
            "generated_output_id": str(output.id),
            "output_version_id": str(version.id),
            "output_version_number": version.version_number,
            "output_sha256": hashlib.sha256(version.content_text.encode()).hexdigest(),
            "supporting_document_version_ids": sorted(str(item) for item in supporting_document_version_ids),
            "supporting_export_ids": sorted(str(item) for item in supporting_export_ids),
            "criteria": cycle.criteria_snapshot,
        }
        canonical = json.dumps(manifest, sort_keys=True, separators=(",", ":"))
        pack = ReviewPack(
            id=uuid4(),
            tenant_id=self.context.tenant_id,
            review_cycle_id=cycle.id,
            round_number=cycle.current_round,
            created_by_user_id=self.context.user_id,
            manifest=manifest,
            manifest_sha256=hashlib.sha256(canonical.encode()).hexdigest(),
            sealed_at=now,
        )
        self.session.add(pack)
        await self.session.flush()
        self.session.add(
            ReviewPackItem(
                id=uuid4(),
                tenant_id=self.context.tenant_id,
                review_pack_id=pack.id,
                item_type="generated_output_version",
                label=output.title,
                generated_output_id=output.id,
                output_version_id=version.id,
                required=True,
                checksum_sha256=manifest["output_sha256"],
                item_metadata={"version_number": version.version_number},
            )
        )
        for document_id in supporting_document_version_ids:
            self.session.add(
                ReviewPackItem(
                    id=uuid4(), tenant_id=self.context.tenant_id, review_pack_id=pack.id,
                    item_type="document_version", label="Supporting document", document_version_id=document_id,
                    required=False, item_metadata={},
                )
            )
        for export_id in supporting_export_ids:
            self.session.add(
                ReviewPackItem(
                    id=uuid4(), tenant_id=self.context.tenant_id, review_pack_id=pack.id,
                    item_type="export", label="Supporting export", export_job_id=export_id,
                    required=False, item_metadata={},
                )
            )
        return pack

    async def _require_reviewer_role(self, user_id: UUID, role_code: str) -> None:
        now = datetime.now(timezone.utc)
        exists = await self.session.scalar(
            select(RoleAssignment.id)
            .join(Role, Role.id == RoleAssignment.role_id)
            .join(
                Membership,
                (Membership.tenant_id == RoleAssignment.tenant_id)
                & (Membership.user_id == RoleAssignment.user_id),
            )
            .where(
                RoleAssignment.tenant_id == self.context.tenant_id,
                RoleAssignment.user_id == user_id,
                Role.code == role_code,
                Membership.status == "active",
                RoleAssignment.valid_from <= now,
                (RoleAssignment.valid_until.is_(None) | (RoleAssignment.valid_until > now)),
                RoleAssignment.revoked_at.is_(None),
            )
        )
        if exists is None:
            raise HTTPException(
                status_code=422,
                detail="The assignee does not hold the requested active reviewer role in this institution.",
            )

    async def _require_task_access(self, task: AssignedReviewTask, action: str) -> None:
        if task.assigned_user_id != self.context.user_id:
            raise HTTPException(status_code=403, detail="Review access is limited to the assigned reviewer.")
        permission = "review_tasks.perform"
        await self.authorization.require_permission(
            tenant_id=self.context.tenant_id,
            user_id=self.context.user_id,
            permission_code=permission,
        )
        if task.external_access_grant_id:
            cycle = await self._cycle(task.review_cycle_id)
            await self._require_external_grant(
                grant_id=task.external_access_grant_id,
                user_id=self.context.user_id,
                action=action,
                identifiers={
                    "review_task_id": task.id,
                    "review_cycle_id": task.review_cycle_id,
                    "output_version_id": task.target_id,
                    "generated_output_id": cycle.generated_output_id,
                    "module_offering_id": cycle.module_offering_id,
                },
            )

    async def _require_external_grant(
        self,
        *,
        grant_id: UUID | None,
        user_id: UUID,
        action: str,
        identifiers: dict[str, UUID | None],
    ) -> ExternalAccessGrant:
        if grant_id is None:
            raise HTTPException(status_code=403, detail="A scoped external access grant is required.")
        grant = await self.session.scalar(
            select(ExternalAccessGrant).where(
                ExternalAccessGrant.tenant_id == self.context.tenant_id,
                ExternalAccessGrant.id == grant_id,
                ExternalAccessGrant.external_user_id == user_id,
            )
        )
        now = datetime.now(timezone.utc)
        if grant is None or grant.status != "active" or not (grant.starts_at <= now < grant.expires_at):
            raise HTTPException(status_code=403, detail="External review access is inactive, expired, or revoked.")
        if not ExternalReviewScope.permits(
            allowed_actions=grant.allowed_actions,
            resource_scope=grant.resource_scope,
            action=action,
            identifiers=identifiers,
        ):
            raise HTTPException(status_code=403, detail="The external grant does not permit this review action or resource.")
        return grant

    async def _cycle(self, cycle_id: UUID | None, lock: bool = False) -> ReviewCycle:
        if cycle_id is None:
            raise HTTPException(status_code=404, detail="Review cycle not found.")
        statement = select(ReviewCycle).where(
            ReviewCycle.tenant_id == self.context.tenant_id,
            ReviewCycle.id == cycle_id,
        )
        if lock:
            statement = statement.with_for_update()
        cycle = await self.session.scalar(statement)
        if cycle is None:
            raise HTTPException(status_code=404, detail="Review cycle not found.")
        return cycle

    async def _task(self, task_id: UUID, lock: bool = False) -> AssignedReviewTask:
        statement = select(AssignedReviewTask).where(
            AssignedReviewTask.tenant_id == self.context.tenant_id,
            AssignedReviewTask.id == task_id,
        )
        if lock:
            statement = statement.with_for_update()
        task = await self.session.scalar(statement)
        if task is None:
            raise HTTPException(status_code=404, detail="Review task not found.")
        return task

    async def _finding_with_task(self, finding_id: UUID) -> tuple[ReviewFinding, AssignedReviewTask]:
        row = (
            await self.session.execute(
                select(ReviewFinding, AssignedReviewTask)
                .join(AssignedReviewTask, AssignedReviewTask.id == ReviewFinding.review_task_id)
                .where(
                    ReviewFinding.tenant_id == self.context.tenant_id,
                    AssignedReviewTask.tenant_id == self.context.tenant_id,
                    ReviewFinding.id == finding_id,
                )
            )
        ).first()
        if row is None:
            raise HTTPException(status_code=404, detail="Review finding not found.")
        return row

    async def _output_row(self, output_id: UUID):
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
        return row

    async def _require_cycle_visibility(self, cycle: ReviewCycle) -> None:
        tasks = await self.session.scalar(
            select(func.count(AssignedReviewTask.id)).where(
                AssignedReviewTask.tenant_id == self.context.tenant_id,
                AssignedReviewTask.review_cycle_id == cycle.id,
                AssignedReviewTask.assigned_user_id == self.context.user_id,
            )
        )
        if tasks:
            return
        output, conversation, lifecycle = await self._output_row(cycle.generated_output_id)
        if conversation.owner_user_id == self.context.user_id:
            return
        await self.authorization.require_permission(
            tenant_id=self.context.tenant_id,
            user_id=self.context.user_id,
            permission_code="review_tasks.read",
            scope_type="module_offering" if lifecycle.module_offering_id else None,
            scope_id=lifecycle.module_offering_id,
        )

    async def _current_round_tasks(self, cycle: ReviewCycle) -> list[AssignedReviewTask]:
        return list(
            await self.session.scalars(
                select(AssignedReviewTask).where(
                    AssignedReviewTask.tenant_id == self.context.tenant_id,
                    AssignedReviewTask.review_cycle_id == cycle.id,
                    AssignedReviewTask.round_number == cycle.current_round,
                )
            )
        )
