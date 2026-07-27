from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from services.database.models import BackgroundJob, BackgroundJobAttempt, DeadLetterJob


ALLOWED_JOB_TYPES = {
    "analytics.generate_report",
    "audit.generate_export",
    "content.ingest_document",
    "content.generate_export",
    "external_access.expire",
    "governance.apply_retention",
    "notifications.dispatch",
    "outbox.publish",
    "operations.backup",
    "operations.restore_drill",
    "communications.deliver_email",
    "integrations.sync",
    "privacy.execute_deletion",
    "data.acquire_dataset",
}


def retry_delay_seconds(attempt_number: int, *, base_seconds: int = 5, maximum_seconds: int = 3600) -> int:
    if attempt_number < 1:
        raise ValueError("attempt_number must be positive")
    return min(maximum_seconds, base_seconds * (2 ** (attempt_number - 1)))


@dataclass(frozen=True, slots=True)
class ClaimedJob:
    job: BackgroundJob
    attempt: BackgroundJobAttempt


class JobQueueService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def enqueue(
        self,
        *,
        tenant_id: UUID,
        job_type: str,
        payload: dict,
        requested_by_user_id: UUID | None,
        correlation_id: str | None,
        queue_name: str = "default",
        priority: int = 100,
        max_attempts: int = 5,
        idempotency_key: str | None = None,
        available_at: datetime | None = None,
    ) -> BackgroundJob:
        if job_type not in ALLOWED_JOB_TYPES:
            raise ValueError(f"Unsupported background job type: {job_type}")
        if idempotency_key:
            existing = await self.session.scalar(
                select(BackgroundJob).where(
                    BackgroundJob.tenant_id == tenant_id,
                    BackgroundJob.idempotency_key == idempotency_key,
                )
            )
            if existing:
                return existing
        job = BackgroundJob(
            id=uuid4(), tenant_id=tenant_id, job_type=job_type, queue_name=queue_name,
            status="queued", priority=priority, payload=payload, result_payload={},
            idempotency_key=idempotency_key, correlation_id=correlation_id,
            requested_by_user_id=requested_by_user_id,
            available_at=available_at or datetime.now(timezone.utc), max_attempts=max_attempts,
        )
        self.session.add(job)
        await self.session.flush()
        return job

    async def claim_next_service_worker(
        self, *, worker_id: str, queue_name: str = "default", lease_seconds: int = 120
    ) -> ClaimedJob | None:
        """Claim across tenants through the restricted SECURITY DEFINER function.

        The function returns one tenant/job pair. This transaction then sets a
        tenant-local RLS context before loading and updating the job attempt.
        The worker database role has no BYPASSRLS privilege.
        """
        row = (
            await self.session.execute(
                text(
                    "SELECT job_id, tenant_id FROM operations.claim_next_job("
                    ":worker_id, :queue_name, :lease_seconds)"
                ),
                {
                    "worker_id": worker_id,
                    "queue_name": queue_name,
                    "lease_seconds": lease_seconds,
                },
            )
        ).first()
        if row is None:
            return None
        await self.session.execute(
            text("SELECT set_config('app.tenant_id', :tenant_id, true)"),
            {"tenant_id": str(row.tenant_id)},
        )
        job = await self.session.scalar(
            select(BackgroundJob).where(
                BackgroundJob.tenant_id == row.tenant_id,
                BackgroundJob.id == row.job_id,
            )
        )
        if job is None:
            raise RuntimeError("Claimed background job could not be reloaded under tenant RLS.")
        now = datetime.now(timezone.utc)
        attempt = BackgroundJobAttempt(
            id=uuid4(), tenant_id=job.tenant_id, job_id=job.id,
            attempt_number=job.attempt_count, worker_id=worker_id,
            status="running", started_at=now, metrics={},
        )
        self.session.add(attempt)
        await self.session.flush()
        return ClaimedJob(job=job, attempt=attempt)

    async def claim_next(self, *, worker_id: str, queue_name: str = "default", lease_seconds: int = 120) -> ClaimedJob | None:
        now = datetime.now(timezone.utc)
        statement = (
            select(BackgroundJob)
            .where(
                BackgroundJob.queue_name == queue_name,
                BackgroundJob.status.in_(("queued", "retry")),
                BackgroundJob.available_at <= now,
            )
            .order_by(BackgroundJob.priority.asc(), BackgroundJob.created_at.asc())
            .with_for_update(skip_locked=True)
            .limit(1)
        )
        job = await self.session.scalar(statement)
        if job is None:
            return None
        job.status = "running"
        job.locked_at = now
        job.locked_by = worker_id
        job.lease_expires_at = now + timedelta(seconds=lease_seconds)
        job.attempt_count += 1
        attempt = BackgroundJobAttempt(
            id=uuid4(), tenant_id=job.tenant_id, job_id=job.id,
            attempt_number=job.attempt_count, worker_id=worker_id,
            status="running", started_at=now, metrics={},
        )
        self.session.add(attempt)
        await self.session.flush()
        return ClaimedJob(job=job, attempt=attempt)

    async def succeed(self, claimed: ClaimedJob, result: dict | None = None) -> None:
        now = datetime.now(timezone.utc)
        claimed.job.status = "completed"
        claimed.job.result_payload = result or {}
        claimed.job.completed_at = now
        claimed.job.locked_at = None
        claimed.job.locked_by = None
        claimed.job.lease_expires_at = None
        claimed.job.last_error_code = None
        claimed.job.last_error_detail = None
        claimed.attempt.status = "completed"
        claimed.attempt.ended_at = now
        await self.session.flush()

    async def fail(self, claimed: ClaimedJob, *, error_code: str, safe_error_detail: str) -> None:
        now = datetime.now(timezone.utc)
        job = claimed.job
        claimed.attempt.status = "failed"
        claimed.attempt.ended_at = now
        claimed.attempt.error_code = error_code
        claimed.attempt.error_detail = safe_error_detail[:4000]
        job.last_error_code = error_code
        job.last_error_detail = safe_error_detail[:4000]
        job.locked_at = None
        job.locked_by = None
        job.lease_expires_at = None
        if job.attempt_count >= job.max_attempts:
            job.status = "dead_letter"
            self.session.add(
                DeadLetterJob(
                    id=uuid4(), tenant_id=job.tenant_id, original_job_id=job.id,
                    job_type=job.job_type, payload=job.payload, failed_at=now,
                    failure_reason=safe_error_detail[:4000], attempt_count=job.attempt_count,
                )
            )
        else:
            job.status = "retry"
            job.available_at = now + timedelta(seconds=retry_delay_seconds(job.attempt_count))
        await self.session.flush()

    async def enqueue_due_schedules_service_worker(self, *, limit: int = 100) -> int:
        """Materialise due interval schedules through a restricted SECURITY DEFINER function."""
        value = await self.session.scalar(
            text("SELECT operations.enqueue_due_scheduled_jobs(:limit)"),
            {"limit": max(1, min(limit, 1000))},
        )
        return int(value or 0)

    async def recover_expired_service_leases(self) -> int:
        """Recover cross-tenant leases through the restricted database function."""
        value = await self.session.scalar(
            text("SELECT operations.recover_expired_job_leases()")
        )
        return int(value or 0)

    async def recover_expired_leases(self) -> int:
        now = datetime.now(timezone.utc)
        jobs = list(
            await self.session.scalars(
                select(BackgroundJob).where(
                    BackgroundJob.status == "running",
                    BackgroundJob.lease_expires_at.is_not(None),
                    BackgroundJob.lease_expires_at <= now,
                ).with_for_update(skip_locked=True)
            )
        )
        for job in jobs:
            job.status = "retry" if job.attempt_count < job.max_attempts else "dead_letter"
            job.available_at = now
            job.locked_at = None
            job.locked_by = None
            job.lease_expires_at = None
            job.last_error_code = "worker_lease_expired"
            job.last_error_detail = "The worker lease expired before the job was acknowledged."
        await self.session.flush()
        return len(jobs)
