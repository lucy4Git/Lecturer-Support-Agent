from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Query

from ..core.dependencies import CurrentContext, DatabaseSession
from ..schemas.operations import (
    BackgroundJobCreate, BackgroundJobResponse, BackupRunCreate, BackupRunResponse,
    JobRetryResponse, NotificationDeliveryResponse, OperationsSummary,
    RestoreDrillCreate, RestoreDrillResponse, RetentionRunCreate, RetentionRunResponse,
    ScheduledJobCreate, ScheduledJobResponse, ScheduledJobUpdate,
)
from ..services.operations import OperationsService

router = APIRouter(prefix="/operations", tags=["operational reliability"])


@router.get("/jobs", response_model=list[BackgroundJobResponse])
async def list_jobs(
    session: DatabaseSession,
    context: CurrentContext,
    status_filter: str | None = Query(default=None, alias="status"),
    limit: int = Query(default=50, ge=1, le=200),
):
    return await OperationsService(session, context).list_jobs(status_filter=status_filter, limit=limit)


@router.post("/jobs", response_model=BackgroundJobResponse, status_code=202)
async def create_job(payload: BackgroundJobCreate, session: DatabaseSession, context: CurrentContext):
    return await OperationsService(session, context).create_job(payload)


@router.get("/summary", response_model=OperationsSummary)
async def operations_summary(session: DatabaseSession, context: CurrentContext):
    return await OperationsService(session, context).summary()


@router.post("/dead-letters/{dead_letter_id}/replay", response_model=JobRetryResponse)
async def replay_dead_letter(dead_letter_id: UUID, session: DatabaseSession, context: CurrentContext):
    dead, replay = await OperationsService(session, context).replay_dead_letter(dead_letter_id)
    return {"original_job_id": dead.original_job_id, "replay_job": replay}


@router.get("/backups", response_model=list[BackupRunResponse])
async def list_backups(
    session: DatabaseSession,
    context: CurrentContext,
    limit: int = Query(default=50, ge=1, le=200),
):
    return await OperationsService(session, context).list_backups(limit)


@router.post("/backups", response_model=BackupRunResponse, status_code=202)
async def request_backup(
    payload: BackupRunCreate, session: DatabaseSession, context: CurrentContext
):
    return await OperationsService(session, context).request_backup(payload)


@router.post(
    "/backups/{backup_run_id}/restore-drills",
    response_model=RestoreDrillResponse,
    status_code=202,
)
async def request_restore_drill(
    backup_run_id: UUID,
    payload: RestoreDrillCreate,
    session: DatabaseSession,
    context: CurrentContext,
):
    return await OperationsService(session, context).request_restore_drill(backup_run_id, payload)


@router.get("/schedules", response_model=list[ScheduledJobResponse])
async def list_schedules(session: DatabaseSession, context: CurrentContext):
    return await OperationsService(session, context).list_schedules()


@router.post("/schedules", response_model=ScheduledJobResponse, status_code=201)
async def create_schedule(payload: ScheduledJobCreate, session: DatabaseSession, context: CurrentContext):
    return await OperationsService(session, context).create_schedule(payload)


@router.patch("/schedules/{schedule_id}", response_model=ScheduledJobResponse)
async def update_schedule(
    schedule_id: UUID, payload: ScheduledJobUpdate,
    session: DatabaseSession, context: CurrentContext,
):
    return await OperationsService(session, context).update_schedule(schedule_id, payload)


@router.get("/notification-deliveries", response_model=list[NotificationDeliveryResponse])
async def list_notification_deliveries(
    session: DatabaseSession, context: CurrentContext,
    limit: int = Query(default=100, ge=1, le=500),
):
    return await OperationsService(session, context).list_notification_deliveries(limit)


@router.get("/retention-runs", response_model=list[RetentionRunResponse])
async def list_retention_runs(
    session: DatabaseSession, context: CurrentContext,
    limit: int = Query(default=50, ge=1, le=200),
):
    return await OperationsService(session, context).list_retention_runs(limit)


@router.post("/retention-runs", response_model=RetentionRunResponse, status_code=202)
async def request_retention_run(
    payload: RetentionRunCreate, session: DatabaseSession, context: CurrentContext,
):
    return await OperationsService(session, context).request_retention_run(payload)
