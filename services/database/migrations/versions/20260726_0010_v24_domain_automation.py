"""Add v2.4 durable notification delivery, retention evidence, and schedule dispatch.

Revision ID: 20260726_0010
Revises: 20260726_0009
"""
from __future__ import annotations

from pathlib import Path
from typing import Sequence

from alembic import op

from services.database.models import NotificationDelivery, RetentionRun, RetentionRunItem

revision: str = "20260726_0010"
down_revision: str | None = "20260726_0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

NEW_TABLES = (
    NotificationDelivery.__table__,
    RetentionRun.__table__,
    RetentionRunItem.__table__,
)


def upgrade() -> None:
    op.execute('CREATE SCHEMA IF NOT EXISTS "governance"')
    op.execute('CREATE SCHEMA IF NOT EXISTS "privacy"')
    op.execute('GRANT USAGE ON SCHEMA governance, privacy, operations TO lsa_app, lsa_worker')
    bind = op.get_bind()
    for table in NEW_TABLES:
        table.create(bind=bind, checkfirst=True)
    op.execute(
        "GRANT SELECT, INSERT, UPDATE, DELETE ON "
        "governance.notification_deliveries, privacy.retention_runs, privacy.retention_run_items TO lsa_app"
    )
    op.execute(
        "GRANT SELECT, INSERT, UPDATE ON "
        "governance.notification_deliveries, privacy.retention_runs, privacy.retention_run_items TO lsa_worker"
    )
    op.execute(
        r"""
        CREATE OR REPLACE FUNCTION operations.enqueue_due_scheduled_jobs(p_limit integer DEFAULT 100)
        RETURNS integer
        LANGUAGE plpgsql
        SECURITY DEFINER
        SET search_path = pg_catalog, operations
        AS $function$
        DECLARE
            inserted_count integer := 0;
        BEGIN
            WITH due AS (
                SELECT s.id, s.tenant_id, s.job_type, s.payload, s.next_run_at,
                       s.interval_seconds
                  FROM operations.scheduled_jobs AS s
                 WHERE s.is_enabled = true
                   AND s.schedule_kind = 'interval'
                   AND s.interval_seconds IS NOT NULL
                   AND s.interval_seconds > 0
                   AND s.next_run_at IS NOT NULL
                   AND s.next_run_at <= now()
                 ORDER BY s.next_run_at ASC
                 FOR UPDATE SKIP LOCKED
                 LIMIT GREATEST(1, LEAST(p_limit, 1000))
            ), queued AS (
                INSERT INTO operations.background_jobs (
                    id, tenant_id, job_type, queue_name, status, priority, payload,
                    result_payload, idempotency_key, available_at, attempt_count,
                    max_attempts, created_at, updated_at
                )
                SELECT gen_random_uuid(), due.tenant_id, due.job_type, 'default', 'queued', 100,
                       due.payload, '{}'::jsonb,
                       'schedule:' || due.id::text || ':' || extract(epoch from due.next_run_at)::bigint::text,
                       now(), 0, 5, now(), now()
                  FROM due
                ON CONFLICT (tenant_id, idempotency_key) DO NOTHING
                RETURNING id
            ), advanced AS (
                UPDATE operations.scheduled_jobs AS schedule
                   SET last_run_at = schedule.next_run_at,
                       next_run_at = schedule.next_run_at + make_interval(secs => schedule.interval_seconds),
                       updated_at = now()
                  FROM due
                 WHERE schedule.id = due.id
                RETURNING schedule.id
            )
            SELECT count(*) INTO inserted_count FROM queued;
            RETURN inserted_count;
        END
        $function$;
        REVOKE ALL ON FUNCTION operations.enqueue_due_scheduled_jobs(integer) FROM PUBLIC;
        GRANT EXECUTE ON FUNCTION operations.enqueue_due_scheduled_jobs(integer) TO lsa_worker;
        """
    )
    policy_file = Path(__file__).resolve().parents[2] / "policies" / "row_level_security.sql"
    op.execute(policy_file.read_text(encoding="utf-8"))


def downgrade() -> None:
    op.execute('DROP FUNCTION IF EXISTS operations.enqueue_due_scheduled_jobs(integer)')
    bind = op.get_bind()
    for table in reversed(NEW_TABLES):
        table.drop(bind=bind, checkfirst=True)
