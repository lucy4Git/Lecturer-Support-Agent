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

    op.add_column("assigned_review_tasks", sa.Column("review_cycle_id", sa.Uuid(), nullable=True), schema="review")
    op.add_column("assigned_review_tasks", sa.Column("review_pack_id", sa.Uuid(), nullable=True), schema="review")
    op.add_column("assigned_review_tasks", sa.Column("reviewer_role_code", sa.String(80), nullable=True), schema="review")
    op.add_column("assigned_review_tasks", sa.Column("review_kind", sa.String(60), nullable=True), schema="review")
    op.add_column("assigned_review_tasks", sa.Column("round_number", sa.Integer(), nullable=False, server_default="1"), schema="review")
    op.add_column("assigned_review_tasks", sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True), schema="review")
    op.add_column("assigned_review_tasks", sa.Column("started_at", sa.DateTime(timezone=True), nullable=True), schema="review")
    op.add_column("assigned_review_tasks", sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True), schema="review")
    op.add_column("assigned_review_tasks", sa.Column("metadata", sa.dialects.postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")), schema="review")
    op.create_foreign_key(
        "fk_assigned_review_tasks_review_cycle_id_review_cycles",
        "assigned_review_tasks", "review_cycles", ["review_cycle_id"], ["id"],
        source_schema="review", referent_schema="review",
    )
    op.create_foreign_key(
        "fk_assigned_review_tasks_review_pack_id_review_packs",
        "assigned_review_tasks", "review_packs", ["review_pack_id"], ["id"],
        source_schema="review", referent_schema="review",
    )
    op.create_index(
        "ix_review_task_cycle_round", "assigned_review_tasks",
        ["tenant_id", "review_cycle_id", "round_number"], schema="review",
    )

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
