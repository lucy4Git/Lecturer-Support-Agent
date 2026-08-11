"""make user name fields optional for staging self-registration

Revision ID: 20260803_0013
Revises: 20260803_0012
Create Date: 2026-08-11
"""
from __future__ import annotations

from alembic import op

revision: str = "20260803_0013"
down_revision: str | None = "20260803_0012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column("users", "given_name", nullable=True, schema="iam")
    op.alter_column("users", "family_name", nullable=True, schema="iam")
    op.alter_column("users", "display_name", nullable=True, schema="iam")


def downgrade() -> None:
    # Restore NOT NULL with empty-string placeholders where values are absent.
    op.execute("UPDATE iam.users SET given_name = '' WHERE given_name IS NULL")
    op.execute("UPDATE iam.users SET family_name = '' WHERE family_name IS NULL")
    op.execute("UPDATE iam.users SET display_name = '' WHERE display_name IS NULL")
    op.alter_column("users", "given_name", nullable=False, schema="iam")
    op.alter_column("users", "family_name", nullable=False, schema="iam")
    op.alter_column("users", "display_name", nullable=False, schema="iam")
