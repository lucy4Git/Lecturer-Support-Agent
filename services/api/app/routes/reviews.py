from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Query, status

from ..core.dependencies import CurrentContext, DatabaseSession
from ..schemas.reviews import (
    CorrectionResubmissionCreate,
    DepartmentReviewDashboardRead,
    ReviewCycleCreate,
    ReviewCycleRead,
    ReviewDecisionCreate,
    ReviewDecisionRead,
    ReviewFindingCreate,
    ReviewFindingRead,
    ReviewFindingResponseCreate,
    ReviewFindingResponseRead,
    ReviewFindingUpdate,
    ReviewPackItemRead,
    ReviewSubmissionCreate,
    ReviewSubmissionRead,
    ReviewTaskActionRequest,
    ReviewTaskRead,
)
from ..services.moderation_review import ModerationReviewService, ReviewAssignee

router = APIRouter(prefix="/reviews", tags=["moderation and external review"])


def _cycle_read(row) -> ReviewCycleRead:
    cycle, tasks, items, open_findings, blocking_findings = row
    data = ReviewCycleRead.model_validate(cycle).model_dump()
    data.update(
        tasks=[ReviewTaskRead.model_validate(item) for item in tasks],
        pack_items=[ReviewPackItemRead.model_validate(item) for item in items],
        open_findings=open_findings,
        blocking_findings=blocking_findings,
    )
    return ReviewCycleRead(**data)


@router.post("/cycles", response_model=ReviewCycleRead, status_code=status.HTTP_201_CREATED)
async def create_review_cycle(
    payload: ReviewCycleCreate, session: DatabaseSession, context: CurrentContext
) -> ReviewCycleRead:
    service = ModerationReviewService(session, context)
    cycle = await service.create_cycle(
        generated_output_id=payload.generated_output_id,
        review_kind=payload.review_kind,
        due_at=payload.due_at,
        instructions=payload.instructions,
        criteria=payload.criteria,
        assignees=[
            ReviewAssignee(
                user_id=item.user_id,
                reviewer_role_code=item.reviewer_role_code,
                external_access_grant_id=item.external_access_grant_id,
            )
            for item in payload.assignees
        ],
        supporting_document_version_ids=payload.supporting_document_version_ids,
        supporting_export_ids=payload.supporting_export_ids,
    )
    return _cycle_read(await service.get_cycle(cycle.id))


@router.get("/cycles/{cycle_id}", response_model=ReviewCycleRead)
async def get_review_cycle(
    cycle_id: UUID, session: DatabaseSession, context: CurrentContext
) -> ReviewCycleRead:
    return _cycle_read(await ModerationReviewService(session, context).get_cycle(cycle_id))


@router.get("/cycles/{cycle_id}/findings", response_model=list[ReviewFindingRead])
async def list_review_findings(
    cycle_id: UUID, session: DatabaseSession, context: CurrentContext
) -> list[ReviewFindingRead]:
    rows = await ModerationReviewService(session, context).list_findings(cycle_id)
    return [ReviewFindingRead.model_validate(item) for item in rows]


@router.get("/tasks", response_model=list[ReviewTaskRead])
async def list_review_tasks(
    session: DatabaseSession,
    context: CurrentContext,
    task_status: str | None = Query(default=None, alias="status"),
    limit: int = Query(default=100, ge=1, le=250),
) -> list[ReviewTaskRead]:
    rows = await ModerationReviewService(session, context).list_my_tasks(task_status, limit)
    return [ReviewTaskRead.model_validate(item) for item in rows]


@router.get("/tasks/{task_id}", response_model=ReviewTaskRead)
async def get_review_task(
    task_id: UUID, session: DatabaseSession, context: CurrentContext
) -> ReviewTaskRead:
    return ReviewTaskRead.model_validate(
        await ModerationReviewService(session, context).get_task(task_id)
    )


@router.post("/tasks/{task_id}/accept", response_model=ReviewTaskRead)
async def accept_review_task(
    task_id: UUID,
    payload: ReviewTaskActionRequest,
    session: DatabaseSession,
    context: CurrentContext,
) -> ReviewTaskRead:
    return ReviewTaskRead.model_validate(
        await ModerationReviewService(session, context).task_action(task_id, "accept", payload.reason)
    )


@router.post("/tasks/{task_id}/start", response_model=ReviewTaskRead)
async def start_review_task(
    task_id: UUID,
    payload: ReviewTaskActionRequest,
    session: DatabaseSession,
    context: CurrentContext,
) -> ReviewTaskRead:
    return ReviewTaskRead.model_validate(
        await ModerationReviewService(session, context).task_action(task_id, "start", payload.reason)
    )


@router.post("/tasks/{task_id}/findings", response_model=ReviewFindingRead, status_code=status.HTTP_201_CREATED)
async def create_review_finding(
    task_id: UUID,
    payload: ReviewFindingCreate,
    session: DatabaseSession,
    context: CurrentContext,
) -> ReviewFindingRead:
    finding = await ModerationReviewService(session, context).create_finding(
        task_id, payload.model_dump()
    )
    return ReviewFindingRead.model_validate(finding)


@router.patch("/findings/{finding_id}", response_model=ReviewFindingRead)
async def update_review_finding(
    finding_id: UUID,
    payload: ReviewFindingUpdate,
    session: DatabaseSession,
    context: CurrentContext,
) -> ReviewFindingRead:
    finding = await ModerationReviewService(session, context).update_finding(
        finding_id, payload.model_dump(exclude_unset=True)
    )
    return ReviewFindingRead.model_validate(finding)


@router.post(
    "/findings/{finding_id}/responses",
    response_model=ReviewFindingResponseRead,
    status_code=status.HTTP_201_CREATED,
)
async def respond_to_review_finding(
    finding_id: UUID,
    payload: ReviewFindingResponseCreate,
    session: DatabaseSession,
    context: CurrentContext,
) -> ReviewFindingResponseRead:
    row = await ModerationReviewService(session, context).respond_to_finding(
        finding_id,
        response_type=payload.response_type,
        body=payload.body,
        related_output_version_id=payload.related_output_version_id,
        metadata=payload.metadata,
    )
    return ReviewFindingResponseRead.model_validate(row)


@router.post("/tasks/{task_id}/submit", response_model=ReviewSubmissionRead, status_code=status.HTTP_201_CREATED)
async def submit_review(
    task_id: UUID,
    payload: ReviewSubmissionCreate,
    session: DatabaseSession,
    context: CurrentContext,
) -> ReviewSubmissionRead:
    row = await ModerationReviewService(session, context).submit_review(
        task_id,
        recommendation=payload.recommendation,
        summary=payload.summary,
        criterion_assessments=payload.criterion_assessments,
        declaration_accepted=payload.declaration_accepted,
    )
    return ReviewSubmissionRead.model_validate(row)


@router.post("/cycles/{cycle_id}/decision", response_model=ReviewDecisionRead, status_code=status.HTTP_201_CREATED)
async def record_review_decision(
    cycle_id: UUID,
    payload: ReviewDecisionCreate,
    session: DatabaseSession,
    context: CurrentContext,
) -> ReviewDecisionRead:
    row = await ModerationReviewService(session, context).record_decision(
        cycle_id,
        decision=payload.decision,
        reason=payload.reason,
        conditions=payload.conditions,
        correction_due_at=payload.correction_due_at,
    )
    return ReviewDecisionRead.model_validate(row)


@router.post("/cycles/{cycle_id}/resubmit", response_model=ReviewCycleRead)
async def resubmit_review_corrections(
    cycle_id: UUID,
    payload: CorrectionResubmissionCreate,
    session: DatabaseSession,
    context: CurrentContext,
) -> ReviewCycleRead:
    service = ModerationReviewService(session, context)
    cycle = await service.resubmit_correction(
        cycle_id,
        corrected_output_version_id=payload.corrected_output_version_id,
        resolution_summary=payload.resolution_summary,
    )
    return _cycle_read(await service.get_cycle(cycle.id))


@router.get(
    "/dashboard/departments/{organisational_unit_id}",
    response_model=DepartmentReviewDashboardRead,
)
async def department_review_dashboard(
    organisational_unit_id: UUID,
    session: DatabaseSession,
    context: CurrentContext,
) -> DepartmentReviewDashboardRead:
    data = await ModerationReviewService(session, context).department_dashboard(
        organisational_unit_id
    )
    return DepartmentReviewDashboardRead(**data)
