"""Add v2.1 saved outputs and notifications for the commercial unified workspace.

Revision ID: 20260725_0007
Revises: 20260725_0006
"""
from __future__ import annotations

from pathlib import Path
from typing import Sequence

from alembic import op

from services.database.models import Notification, SavedOutput

revision: str = "20260725_0007"
down_revision: str | None = "20260725_0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

NEW_TABLES = (SavedOutput.__table__, Notification.__table__)


def upgrade() -> None:
    bind = op.get_bind()
    for table in NEW_TABLES:
        table.create(bind=bind, checkfirst=True)
    op.execute(
        "GRANT SELECT, INSERT, UPDATE, DELETE ON conversation.saved_outputs, "
        "governance.notifications TO lsa_app"
    )
    policy_file = Path(__file__).resolve().parents[2] / "policies" / "row_level_security.sql"
    op.execute(policy_file.read_text(encoding="utf-8"))


def downgrade() -> None:
    bind = op.get_bind()
    for table in reversed(NEW_TABLES):
        table.drop(bind=bind, checkfirst=True)
