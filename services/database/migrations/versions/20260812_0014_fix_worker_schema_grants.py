"""fix lsa_worker missing USAGE grants on audit and other schemas

Revision ID: 20260812_0014
Revises: 20260803_0013
Create Date: 2026-08-12
"""
from __future__ import annotations

from alembic import op

revision: str = "20260812_0014"
down_revision: str | None = "20260803_0013"
branch_labels = None
depends_on = None

_WORKER_SCHEMAS = (
    "audit", "content", "conversation", "ai", "source",
    "review", "ingestion", "academic", "analytics", "tenant", "iam"
)


def upgrade() -> None:
    # Earlier migrations missed USAGE grants for lsa_worker on several schemas.
    op.execute(
        "GRANT USAGE ON SCHEMA "
        + ", ".join(_WORKER_SCHEMAS)
        + " TO lsa_worker"
    )
    # Grant INSERT/UPDATE on all tenant-owned tables so the worker can write job
    # outcomes, trace records, notification rows, etc.
    op.execute(
        r"""
        DO $grant_worker_write$
        DECLARE item record;
        BEGIN
          FOR item IN
            SELECT c.table_schema, c.table_name
              FROM information_schema.columns c
             WHERE c.column_name = 'tenant_id'
               AND c.table_schema IN (
                 'audit','content','conversation','ai','source','review',
                 'ingestion','academic','analytics','governance','operations'
               )
             GROUP BY c.table_schema, c.table_name
          LOOP
            EXECUTE format(
              'GRANT INSERT, UPDATE ON %I.%I TO lsa_worker',
              item.table_schema, item.table_name
            );
          END LOOP;
        END
        $grant_worker_write$;
        """
    )
    # background_jobs UPDATE already covered above via operations schema;
    # also need UPDATE on operations.scheduled_jobs for the scheduler helper.
    op.execute(
        "GRANT UPDATE ON operations.background_jobs TO lsa_worker"
    )


def downgrade() -> None:
    op.execute(
        "REVOKE USAGE ON SCHEMA "
        + ", ".join(_WORKER_SCHEMAS)
        + " FROM lsa_worker"
    )
