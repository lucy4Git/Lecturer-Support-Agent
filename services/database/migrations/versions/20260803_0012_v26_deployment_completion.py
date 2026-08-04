"""Add v2.6 deployment-completion and controlled access-request table.

Revision ID: 20260803_0012
Revises: 20260726_0011
"""
from __future__ import annotations

from pathlib import Path
from typing import Sequence

from alembic import op

from services.database.models import InstitutionalAccessRequest

revision: str = "20260803_0012"
down_revision: str | None = "20260726_0011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    InstitutionalAccessRequest.__table__.create(bind=bind, checkfirst=True)
    op.execute(
        "GRANT SELECT, UPDATE ON iam.institutional_access_requests TO lsa_app"
    )
    op.execute(
        "GRANT SELECT, INSERT ON iam.institutional_access_requests TO lsa_auth"
    )
    policy_file = Path(__file__).resolve().parents[2] / "policies" / "row_level_security.sql"
    op.execute(policy_file.read_text(encoding="utf-8"))


def downgrade() -> None:
    InstitutionalAccessRequest.__table__.drop(bind=op.get_bind(), checkfirst=True)
