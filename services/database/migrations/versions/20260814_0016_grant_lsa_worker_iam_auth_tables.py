"""Grant lsa_worker SELECT on iam auth tables needed by AuthorizationService.

The worker calls DocumentIngestionService → DocumentAccessService → AuthorizationService
which queries iam.roles, iam.role_permissions, iam.permissions, and iam.users.

Revision ID: 20260814_0016
Revises: 20260814_0015
Create Date: 2026-08-14
"""
from __future__ import annotations

from alembic import op

revision = "20260814_0016"
down_revision = "20260814_0015"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("GRANT SELECT ON iam.roles TO lsa_worker;")
    op.execute("GRANT SELECT ON iam.role_permissions TO lsa_worker;")
    op.execute("GRANT SELECT ON iam.permissions TO lsa_worker;")
    op.execute("GRANT SELECT ON iam.users TO lsa_worker;")


def downgrade() -> None:
    op.execute("REVOKE SELECT ON iam.roles FROM lsa_worker;")
    op.execute("REVOKE SELECT ON iam.role_permissions FROM lsa_worker;")
    op.execute("REVOKE SELECT ON iam.permissions FROM lsa_worker;")
    op.execute("REVOKE SELECT ON iam.users FROM lsa_worker;")
