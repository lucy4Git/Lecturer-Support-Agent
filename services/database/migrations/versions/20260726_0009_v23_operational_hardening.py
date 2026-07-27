"""Add v2.3 durable jobs, backup evidence, and operational hardening records.

Revision ID: 20260726_0009
Revises: 20260726_0008
"""
from __future__ import annotations

from pathlib import Path
from typing import Sequence

from alembic import op

from services.database.models import (
    BackgroundJob,
    BackgroundJobAttempt,
    BackupRun,
    DeadLetterJob,
    RestoreDrill,
    ScheduledJob,
)

revision: str = "20260726_0009"
down_revision: str | None = "20260726_0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

NEW_TABLES = (
    BackgroundJob.__table__,
    BackgroundJobAttempt.__table__,
    DeadLetterJob.__table__,
    ScheduledJob.__table__,
    BackupRun.__table__,
    RestoreDrill.__table__,
)


def upgrade() -> None:
    op.execute('CREATE SCHEMA IF NOT EXISTS "operations"')
    op.execute('GRANT USAGE ON SCHEMA operations TO lsa_app, lsa_worker')
    bind = op.get_bind()
    for table in NEW_TABLES:
        table.create(bind=bind, checkfirst=True)
    op.execute(
        "GRANT SELECT, INSERT, UPDATE, DELETE ON "
        "operations.background_jobs, operations.background_job_attempts, "
        "operations.dead_letter_jobs, operations.scheduled_jobs, "
        "operations.backup_runs, operations.restore_drills TO lsa_app"
    )
    op.execute(
        "GRANT SELECT, INSERT, UPDATE ON "
        "operations.background_jobs, operations.background_job_attempts, "
        "operations.dead_letter_jobs TO lsa_worker"
    )
    op.execute(
        "ALTER DEFAULT PRIVILEGES IN SCHEMA operations "
        "GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO lsa_app"
    )
    op.execute(
        r"""
        CREATE OR REPLACE FUNCTION operations.claim_next_job(
            p_worker_id text,
            p_queue_name text,
            p_lease_seconds integer
        ) RETURNS TABLE(job_id uuid, tenant_id uuid)
        LANGUAGE plpgsql
        SECURITY DEFINER
        SET search_path = pg_catalog, operations
        AS $function$
        BEGIN
            RETURN QUERY
            WITH candidate AS (
                SELECT j.id
                FROM operations.background_jobs AS j
                WHERE j.queue_name = p_queue_name
                  AND j.status IN ('queued', 'retry')
                  AND j.available_at <= now()
                ORDER BY j.priority ASC, j.created_at ASC
                FOR UPDATE SKIP LOCKED
                LIMIT 1
            )
            UPDATE operations.background_jobs AS job
               SET status = 'running',
                   locked_at = now(),
                   locked_by = p_worker_id,
                   lease_expires_at = now() + make_interval(secs => p_lease_seconds),
                   attempt_count = job.attempt_count + 1,
                   updated_at = now()
              FROM candidate
             WHERE job.id = candidate.id
            RETURNING job.id, job.tenant_id;
        END
        $function$;
        REVOKE ALL ON FUNCTION operations.claim_next_job(text, text, integer) FROM PUBLIC;
        GRANT EXECUTE ON FUNCTION operations.claim_next_job(text, text, integer) TO lsa_worker;
        """
    )
    op.execute(
        r"""
        CREATE OR REPLACE FUNCTION operations.recover_expired_job_leases()
        RETURNS integer
        LANGUAGE plpgsql
        SECURITY DEFINER
        SET search_path = pg_catalog, operations
        AS $function$
        DECLARE
            recovered integer := 0;
        BEGIN
            WITH expired AS (
                SELECT j.id, j.tenant_id, j.job_type, j.payload, j.attempt_count,
                       j.max_attempts
                  FROM operations.background_jobs AS j
                 WHERE j.status = 'running'
                   AND j.lease_expires_at IS NOT NULL
                   AND j.lease_expires_at <= now()
                 FOR UPDATE SKIP LOCKED
            ), updated AS (
                UPDATE operations.background_jobs AS job
                   SET status = CASE
                         WHEN expired.attempt_count >= expired.max_attempts THEN 'dead_letter'
                         ELSE 'retry'
                       END,
                       available_at = now(),
                       locked_at = NULL,
                       locked_by = NULL,
                       lease_expires_at = NULL,
                       last_error_code = 'worker_lease_expired',
                       last_error_detail = 'The worker lease expired before acknowledgement.',
                       updated_at = now()
                  FROM expired
                 WHERE job.id = expired.id
                RETURNING job.id, job.tenant_id, job.job_type, job.payload,
                          job.attempt_count, job.status
            ), attempts AS (
                UPDATE operations.background_job_attempts AS attempt
                   SET status = 'failed',
                       ended_at = now(),
                       error_code = 'worker_lease_expired',
                       error_detail = 'The worker lease expired before acknowledgement.',
                       updated_at = now()
                  FROM updated
                 WHERE attempt.job_id = updated.id
                   AND attempt.status = 'running'
                RETURNING attempt.id
            ), dead_letters AS (
                INSERT INTO operations.dead_letter_jobs (
                    id, tenant_id, original_job_id, job_type, payload, failed_at,
                    failure_reason, attempt_count, created_at, updated_at
                )
                SELECT gen_random_uuid(), updated.tenant_id, updated.id, updated.job_type,
                       updated.payload, now(), 'The worker lease expired after the maximum attempts.',
                       updated.attempt_count, now(), now()
                  FROM updated
                 WHERE updated.status = 'dead_letter'
                ON CONFLICT (tenant_id, original_job_id) DO NOTHING
                RETURNING id
            )
            SELECT count(*) INTO recovered FROM updated;
            RETURN recovered;
        END
        $function$;
        REVOKE ALL ON FUNCTION operations.recover_expired_job_leases() FROM PUBLIC;
        GRANT EXECUTE ON FUNCTION operations.recover_expired_job_leases() TO lsa_worker;
        """
    )
    policy_file = Path(__file__).resolve().parents[2] / "policies" / "row_level_security.sql"
    op.execute(policy_file.read_text(encoding="utf-8"))


def downgrade() -> None:
    bind = op.get_bind()
    for table in reversed(NEW_TABLES):
        table.drop(bind=bind, checkfirst=True)
    op.execute('DROP SCHEMA IF EXISTS "operations" CASCADE')
