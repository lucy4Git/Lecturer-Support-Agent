from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from services.database.models import (
    BackgroundJob, BackupRun, DeadLetterJob, NotificationDelivery, RestoreDrill,
    RetentionRun, ScheduledJob,
)

from ..core.request_context import RequestContext
from ..schemas.operations import (
    BackgroundJobCreate, BackupRunCreate, RestoreDrillCreate, RetentionRunCreate,
    ScheduledJobCreate, ScheduledJobUpdate,
)
from .audit import AuditService
from .authorization import AuthorizationService
from .job_queue import ALLOWED_JOB_TYPES, JobQueueService


class OperationsService:
    def __init__(self, session: AsyncSession, context: RequestContext) -> None:
        self.session = session
        self.context = context
        self.authorization = AuthorizationService(session, context)
        self.audit = AuditService(session, context)

    async def _require_read(self) -> None:
        await self.authorization.require_permission(
            tenant_id=self.context.tenant_id, user_id=self.context.user_id,
            permission_code="operations.jobs.read",
        )

    async def list_jobs(self, *, status_filter: str | None, limit: int) -> list[BackgroundJob]:
        await self._require_read()
        query = select(BackgroundJob).where(BackgroundJob.tenant_id == self.context.tenant_id)
        if status_filter:
            query = query.where(BackgroundJob.status == status_filter)
        return list(await self.session.scalars(query.order_by(BackgroundJob.created_at.desc()).limit(limit)))

    async def create_job(self, payload: BackgroundJobCreate) -> BackgroundJob:
        await self.authorization.require_permission(
            tenant_id=self.context.tenant_id, user_id=self.context.user_id,
            permission_code="operations.jobs.manage",
        )
        job = await JobQueueService(self.session).enqueue(
            tenant_id=self.context.tenant_id, job_type=payload.job_type,
            payload=payload.payload, requested_by_user_id=self.context.user_id,
            correlation_id=self.context.correlation_id, queue_name=payload.queue_name,
            priority=payload.priority, max_attempts=payload.max_attempts,
            idempotency_key=payload.idempotency_key,
        )
        await self.audit.record(action="operations.job_created", resource_type="background_job", resource_id=job.id, after_state={"job_type": job.job_type, "status": job.status})
        return job

    async def summary(self) -> dict:
        await self._require_read()
        rows = (await self.session.execute(
            select(BackgroundJob.status, func.count()).where(BackgroundJob.tenant_id == self.context.tenant_id).group_by(BackgroundJob.status)
        )).all()
        oldest = await self.session.scalar(
            select(func.min(BackgroundJob.created_at)).where(
                BackgroundJob.tenant_id == self.context.tenant_id,
                BackgroundJob.status.in_(("queued", "retry")),
            )
        )
        dead = await self.session.scalar(select(func.count()).select_from(DeadLetterJob).where(DeadLetterJob.tenant_id == self.context.tenant_id))
        return {"counts": {str(key): int(value) for key, value in rows}, "dead_letter_count": int(dead or 0), "oldest_queued_at": oldest}


    async def list_backups(self, limit: int) -> list[BackupRun]:
        await self.authorization.require_permission(
            tenant_id=self.context.tenant_id, user_id=self.context.user_id,
            permission_code="operations.backups.read",
        )
        return list(
            await self.session.scalars(
                select(BackupRun)
                .where(BackupRun.tenant_id == self.context.tenant_id)
                .order_by(BackupRun.created_at.desc())
                .limit(limit)
            )
        )

    async def request_backup(self, payload: BackupRunCreate) -> BackupRun:
        await self.authorization.require_permission(
            tenant_id=self.context.tenant_id, user_id=self.context.user_id,
            permission_code="operations.backups.manage",
        )
        run = BackupRun(
            id=uuid4(), tenant_id=self.context.tenant_id,
            backup_type=payload.backup_type, status="requested",
            requested_by_user_id=self.context.user_id, component_results={},
        )
        self.session.add(run)
        await self.session.flush()
        await JobQueueService(self.session).enqueue(
            tenant_id=self.context.tenant_id,
            job_type="operations.backup",
            payload={
                "backup_run_id": str(run.id),
                "include_object_storage": payload.include_object_storage,
                "include_vector_store": payload.include_vector_store,
            },
            requested_by_user_id=self.context.user_id,
            correlation_id=self.context.correlation_id,
            idempotency_key=f"backup:{run.id}",
        )
        await self.audit.record(
            action="operations.backup_requested", resource_type="backup_run",
            resource_id=run.id, after_state={"backup_type": run.backup_type},
        )
        return run

    async def request_restore_drill(
        self, backup_run_id: UUID, payload: RestoreDrillCreate
    ) -> RestoreDrill:
        await self.authorization.require_permission(
            tenant_id=self.context.tenant_id, user_id=self.context.user_id,
            permission_code="operations.backups.manage",
        )
        backup = await self.session.scalar(
            select(BackupRun).where(
                BackupRun.tenant_id == self.context.tenant_id,
                BackupRun.id == backup_run_id,
            )
        )
        if backup is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Backup run not found.")
        drill = RestoreDrill(
            id=uuid4(), tenant_id=self.context.tenant_id,
            backup_run_id=backup.id, status="requested",
            requested_by_user_id=self.context.user_id,
            isolated_environment=payload.isolated_environment,
            validation_results={},
        )
        self.session.add(drill)
        await self.session.flush()
        await JobQueueService(self.session).enqueue(
            tenant_id=self.context.tenant_id,
            job_type="operations.restore_drill",
            payload={"restore_drill_id": str(drill.id), "backup_run_id": str(backup.id)},
            requested_by_user_id=self.context.user_id,
            correlation_id=self.context.correlation_id,
            idempotency_key=f"restore-drill:{drill.id}",
        )
        await self.audit.record(
            action="operations.restore_drill_requested", resource_type="restore_drill",
            resource_id=drill.id, after_state={"backup_run_id": str(backup.id)},
        )
        return drill

    async def replay_dead_letter(self, dead_letter_id: UUID) -> tuple[DeadLetterJob, BackgroundJob]:
        await self.authorization.require_permission(
            tenant_id=self.context.tenant_id, user_id=self.context.user_id,
            permission_code="operations.jobs.manage",
        )
        dead = await self.session.scalar(
            select(DeadLetterJob).where(DeadLetterJob.tenant_id == self.context.tenant_id, DeadLetterJob.id == dead_letter_id).with_for_update()
        )
        if dead is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dead-letter job not found.")
        if dead.replayed_at is not None:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Dead-letter job has already been replayed.")
        replay = await JobQueueService(self.session).enqueue(
            tenant_id=self.context.tenant_id, job_type=dead.job_type, payload=dead.payload,
            requested_by_user_id=self.context.user_id, correlation_id=self.context.correlation_id,
            idempotency_key=f"replay:{dead.id}",
        )
        dead.replayed_at = datetime.now(timezone.utc)
        dead.replayed_by_user_id = self.context.user_id
        dead.replay_job_id = replay.id
        await self.audit.record(action="operations.dead_letter_replayed", resource_type="dead_letter_job", resource_id=dead.id, after_state={"replay_job_id": str(replay.id)})
        return dead, replay


    async def list_schedules(self) -> list[ScheduledJob]:
        await self.authorization.require_permission(
            tenant_id=self.context.tenant_id, user_id=self.context.user_id,
            permission_code="operations.schedules.read",
        )
        return list(await self.session.scalars(
            select(ScheduledJob).where(ScheduledJob.tenant_id == self.context.tenant_id)
            .order_by(ScheduledJob.code)
        ))

    async def create_schedule(self, payload: ScheduledJobCreate) -> ScheduledJob:
        await self.authorization.require_permission(
            tenant_id=self.context.tenant_id, user_id=self.context.user_id,
            permission_code="operations.schedules.manage",
        )
        if payload.job_type not in ALLOWED_JOB_TYPES:
            raise HTTPException(status_code=422, detail="Unsupported scheduled job type.")
        existing = await self.session.scalar(select(ScheduledJob).where(
            ScheduledJob.tenant_id == self.context.tenant_id, ScheduledJob.code == payload.code
        ))
        if existing is not None:
            raise HTTPException(status_code=409, detail="A schedule with this code already exists.")
        now = datetime.now(timezone.utc)
        item = ScheduledJob(
            id=uuid4(), tenant_id=self.context.tenant_id, code=payload.code,
            job_type=payload.job_type, schedule_kind="interval",
            interval_seconds=payload.interval_seconds, cron_expression=None,
            payload={**payload.payload, "requested_by_role_code": self.context.role_code},
            is_enabled=payload.is_enabled,
            next_run_at=(now + timedelta(seconds=payload.interval_seconds)) if payload.is_enabled else None,
            last_run_at=None, created_by_user_id=self.context.user_id,
        )
        self.session.add(item)
        await self.audit.record(action="operations.schedule_created", resource_type="scheduled_job", resource_id=item.id, after_state={"code": item.code, "job_type": item.job_type})
        await self.session.flush()
        return item

    async def update_schedule(self, schedule_id: UUID, payload: ScheduledJobUpdate) -> ScheduledJob:
        await self.authorization.require_permission(
            tenant_id=self.context.tenant_id, user_id=self.context.user_id,
            permission_code="operations.schedules.manage",
        )
        item = await self.session.scalar(select(ScheduledJob).where(
            ScheduledJob.tenant_id == self.context.tenant_id, ScheduledJob.id == schedule_id
        ).with_for_update())
        if item is None:
            raise HTTPException(status_code=404, detail="Scheduled job not found.")
        before = {"interval_seconds": item.interval_seconds, "is_enabled": item.is_enabled}
        if payload.interval_seconds is not None:
            item.interval_seconds = payload.interval_seconds
        if payload.payload is not None:
            item.payload = {**payload.payload, "requested_by_role_code": self.context.role_code}
        if payload.is_enabled is not None:
            item.is_enabled = payload.is_enabled
        if item.is_enabled and (item.next_run_at is None or payload.interval_seconds is not None):
            item.next_run_at = datetime.now(timezone.utc) + timedelta(seconds=item.interval_seconds or 60)
        if not item.is_enabled:
            item.next_run_at = None
        await self.audit.record(action="operations.schedule_updated", resource_type="scheduled_job", resource_id=item.id, before_state=before, after_state={"interval_seconds": item.interval_seconds, "is_enabled": item.is_enabled})
        await self.session.flush()
        return item

    async def list_notification_deliveries(self, limit: int = 100) -> list[NotificationDelivery]:
        await self.authorization.require_permission(
            tenant_id=self.context.tenant_id, user_id=self.context.user_id,
            permission_code="operations.deliveries.read",
        )
        return list(await self.session.scalars(select(NotificationDelivery).where(
            NotificationDelivery.tenant_id == self.context.tenant_id
        ).order_by(NotificationDelivery.created_at.desc()).limit(limit)))

    async def list_retention_runs(self, limit: int = 50) -> list[RetentionRun]:
        await self.authorization.require_permission(
            tenant_id=self.context.tenant_id, user_id=self.context.user_id,
            permission_code="operations.retention.read",
        )
        return list(await self.session.scalars(select(RetentionRun).where(
            RetentionRun.tenant_id == self.context.tenant_id
        ).order_by(RetentionRun.created_at.desc()).limit(limit)))

    async def request_retention_run(self, payload: RetentionRunCreate) -> RetentionRun:
        await self.authorization.require_permission(
            tenant_id=self.context.tenant_id, user_id=self.context.user_id,
            permission_code="operations.retention.manage",
        )
        run = RetentionRun(
            id=uuid4(), tenant_id=self.context.tenant_id,
            requested_by_user_id=self.context.user_id, status="requested",
            dry_run=payload.dry_run, summary={},
        )
        self.session.add(run); await self.session.flush()
        await JobQueueService(self.session).enqueue(
            tenant_id=self.context.tenant_id, job_type="governance.apply_retention",
            payload={"retention_run_id": str(run.id), "dry_run": payload.dry_run,
                     "max_candidates": payload.max_candidates,
                     "requested_by_role_code": self.context.role_code},
            requested_by_user_id=self.context.user_id,
            correlation_id=self.context.correlation_id,
            idempotency_key=f"retention:{run.id}",
        )
        await self.audit.record(action="retention.run_requested", resource_type="retention_run", resource_id=run.id, after_state={"dry_run": run.dry_run})
        return run
