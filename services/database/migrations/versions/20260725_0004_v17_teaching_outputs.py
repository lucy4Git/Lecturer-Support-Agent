"""Add v1.7 teaching output workflows, module context, safety, and exports.

Revision ID: 20260725_0004
Revises: 20260725_0003
"""
from __future__ import annotations

from pathlib import Path
from typing import Sequence

from alembic import op

from services.database.models import (
    AssessmentSafetyReview,
    ExportJob,
    ModuleContextSnapshot,
    OutputLifecycle,
    OutputWorkflowAction,
)

revision: str = "20260725_0004"
down_revision: str | None = "20260725_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

NEW_TABLES = (
    ModuleContextSnapshot.__table__,
    OutputLifecycle.__table__,
    AssessmentSafetyReview.__table__,
    OutputWorkflowAction.__table__,
    ExportJob.__table__,
)


def upgrade() -> None:
    bind = op.get_bind()
    for table in NEW_TABLES:
        table.create(bind=bind, checkfirst=True)

    op.execute(
        "GRANT SELECT, INSERT, UPDATE, DELETE ON academic.module_context_snapshots, "
        "conversation.output_lifecycles, conversation.output_workflow_actions, "
        "review.assessment_safety_reviews, content.export_jobs TO lsa_app"
    )
    policy_file = Path(__file__).resolve().parents[2] / "policies" / "row_level_security.sql"
    op.execute(policy_file.read_text(encoding="utf-8"))


def downgrade() -> None:
    bind = op.get_bind()
    for table in reversed(NEW_TABLES):
        table.drop(bind=bind, checkfirst=True)
