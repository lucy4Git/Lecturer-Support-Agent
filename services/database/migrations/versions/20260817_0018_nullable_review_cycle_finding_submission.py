"""Make review_cycle_id and source_output_version_id nullable in review findings/submissions.

Enables standalone findings and submissions without requiring a full ReviewCycle chain.
Required for the moderation chat workflow where findings are recorded without a formal cycle.

Revision ID: 20260817_0018
Revises: 20260814_0017
Create Date: 2026-08-17
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260817_0018"
down_revision = "20260814_0017"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column("review_findings", "review_cycle_id",
                    existing_type=sa.UUID(),
                    nullable=True,
                    schema="review")
    op.alter_column("review_findings", "source_output_version_id",
                    existing_type=sa.UUID(),
                    nullable=True,
                    schema="review")
    op.alter_column("review_submissions", "review_cycle_id",
                    existing_type=sa.UUID(),
                    nullable=True,
                    schema="review")


def downgrade() -> None:
    # Only safe to downgrade if no NULL rows exist
    op.alter_column("review_submissions", "review_cycle_id",
                    existing_type=sa.UUID(),
                    nullable=False,
                    schema="review")
    op.alter_column("review_findings", "source_output_version_id",
                    existing_type=sa.UUID(),
                    nullable=False,
                    schema="review")
    op.alter_column("review_findings", "review_cycle_id",
                    existing_type=sa.UUID(),
                    nullable=False,
                    schema="review")
