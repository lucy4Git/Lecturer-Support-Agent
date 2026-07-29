"""Add v1.8 moderation, external review, findings, decisions, and correction rounds.

Revision ID: 20260725_0005
Revises: 20260725_0004
"""
from __future__ import annotations

from pathlib import Path
from typing import Sequence

import sqlalchemy as sa
from alembic import op

from services.database.models import (
    ReviewCorrectionRound,
    ReviewCycle,
    ReviewDecision,
    ReviewFinding,
    ReviewFindingResponse,
    ReviewPack,
    ReviewPackItem,
    ReviewSubmission,
)

revision: str = "20260725_0005"
down_revision: str | None = "20260725_0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

NEW_TABLES = (
    ReviewCycle.__table__,
    ReviewPack.__table__,
    ReviewPackItem.__table__,
    ReviewFinding.__table__,
    ReviewFindingResponse.__table__,
    ReviewSubmission.__table__,
    ReviewDecision.__table__,
    ReviewCorrectionRound.__table__,
)


def upgrade() -> None:
    bind = op.get_bind()
    for table in NEW_TABLES:
        table.create(bind=bind, checkfirst=True)

    # Use IF NOT EXISTS so this migration is idempotent when the first migration's
    # create_all() has already created these columns on a fresh database.
    op.execute("""
        ALTER TABLE review.assigned_review_tasks
            ADD COLUMN IF NOT EXISTS review_cycle_id UUID,
            ADD COLUMN IF NOT EXISTS review_pack_id UUID,
            ADD COLUMN IF NOT EXISTS reviewer_role_code VARCHAR(80),
            ADD COLUMN IF NOT EXISTS review_kind VARCHAR(60),
            ADD COLUMN IF NOT EXISTS round_number INTEGER NOT NULL DEFAULT 1,
            ADD COLUMN IF NOT EXISTS accepted_at TIMESTAMPTZ,
            ADD COLUMN IF NOT EXISTS started_at TIMESTAMPTZ,
            ADD COLUMN IF NOT EXISTS submitted_at TIMESTAMPTZ,
            ADD COLUMN IF NOT EXISTS metadata JSONB NOT NULL DEFAULT '{}'::jsonb
    """)
    op.execute("""
        DO $$ BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_constraint
                WHERE conname = 'fk_assigned_review_tasks_review_cycle_id_review_cycles'
            ) THEN
                ALTER TABLE review.assigned_review_tasks
                    ADD CONSTRAINT fk_assigned_review_tasks_review_cycle_id_review_cycles
                    FOREIGN KEY (review_cycle_id) REFERENCES review.review_cycles(id);
            END IF;
        END $$
    """)
    op.execute("""
        DO $$ BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_constraint
                WHERE conname = 'fk_assigned_review_tasks_review_pack_id_review_packs'
            ) THEN
                ALTER TABLE review.assigned_review_tasks
                    ADD CONSTRAINT fk_assigned_review_tasks_review_pack_id_review_packs
                    FOREIGN KEY (review_pack_id) REFERENCES review.review_packs(id);
            END IF;
        END $$
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_review_task_cycle_round
        ON review.assigned_review_tasks (tenant_id, review_cycle_id, round_number)
    """)

    op.execute(
        "GRANT SELECT, INSERT, UPDATE, DELETE ON review.review_cycles, review.review_packs, "
        "review.review_pack_items, review.review_findings, review.review_finding_responses, "
        "review.review_submissions, review.review_decisions, review.review_correction_rounds "
        "TO lsa_app"
    )
    policy_file = Path(__file__).resolve().parents[2] / "policies" / "row_level_security.sql"
    op.execute(policy_file.read_text(encoding="utf-8"))


def downgrade() -> None:
    op.drop_index("ix_review_task_cycle_round", table_name="assigned_review_tasks", schema="review")
    for name in (
        "fk_assigned_review_tasks_review_pack_id_review_packs",
        "fk_assigned_review_tasks_review_cycle_id_review_cycles",
    ):
        op.drop_constraint(name, "assigned_review_tasks", schema="review", type_="foreignkey")
    for column in (
        "metadata", "submitted_at", "started_at", "accepted_at", "round_number",
        "review_kind", "reviewer_role_code", "review_pack_id", "review_cycle_id",
    ):
        op.drop_column("assigned_review_tasks", column, schema="review")
    bind = op.get_bind()
    for table in reversed(NEW_TABLES):
        table.drop(bind=bind, checkfirst=True)
