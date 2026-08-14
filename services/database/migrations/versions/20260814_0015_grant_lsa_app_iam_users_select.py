"""Grant lsa_app SELECT on iam.users so the CapabilityRegistry workload query can join user display names.

Revision ID: 20260814_0015
Revises: 20260812_0014
Create Date: 2026-08-14
"""
from __future__ import annotations

from alembic import op

revision = "20260814_0015"
down_revision = "20260812_0014"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # lsa_app needs to read iam.users for workload and assignment queries that join user display names.
    # lsa_auth owns the table; grant SELECT only (lsa_app never writes users directly).
    op.execute("GRANT SELECT ON iam.users TO lsa_app;")


def downgrade() -> None:
    op.execute("REVOKE SELECT ON iam.users FROM lsa_app;")
