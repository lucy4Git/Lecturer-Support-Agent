"""Add v1.4 identity, administration, and position-management foundation.

Revision ID: 20260724_0002
Revises: 20260724_0001
"""
from __future__ import annotations

from pathlib import Path
from typing import Sequence

from alembic import op

from services.database.models import (
    AuthenticationSession,
    InvitationRoleGrant,
    MembershipPosition,
    PasswordCredential,
    PositionDefinition,
    UserInvitation,
)

revision: str = "20260724_0002"
down_revision: str | None = "20260724_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

NEW_TABLES = (
    PasswordCredential.__table__,
    PositionDefinition.__table__,
    MembershipPosition.__table__,
    UserInvitation.__table__,
    InvitationRoleGrant.__table__,
    AuthenticationSession.__table__,
)


def upgrade() -> None:
    bind = op.get_bind()
    for table in NEW_TABLES:
        table.create(bind=bind, checkfirst=True)

    op.execute(
        """
        DO $$ BEGIN
          IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'lsa_auth') THEN
            CREATE ROLE lsa_auth NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOBYPASSRLS;
          END IF;
        END $$;
        """
    )
    op.execute("GRANT USAGE ON SCHEMA tenant, iam, audit TO lsa_auth")
    op.execute("GRANT SELECT ON tenant.institutions, iam.roles TO lsa_auth")
    op.execute("GRANT SELECT, INSERT, UPDATE ON iam.users TO lsa_auth")
    op.execute(
        "GRANT SELECT, INSERT, UPDATE ON iam.password_credentials, iam.memberships, "
        "iam.access_scopes, iam.role_assignments, iam.user_invitations, "
        "iam.invitation_role_grants, iam.authentication_sessions TO lsa_auth"
    )
    op.execute("GRANT INSERT ON audit.security_events TO lsa_auth")
    op.execute(
        "GRANT SELECT, INSERT, UPDATE, DELETE ON iam.position_definitions, "
        "iam.membership_positions, iam.user_invitations, iam.invitation_role_grants, "
        "iam.authentication_sessions TO lsa_app"
    )
    op.execute(
        """
        DO $$
        DECLARE item record;
        BEGIN
          FOR item IN
            SELECT c.table_schema, c.table_name
            FROM information_schema.columns c
            WHERE c.column_name = 'tenant_id'
              AND c.table_schema IN ('tenant','iam','academic','ingestion','content',
                  'conversation','ai','source','review','audit','privacy')
            GROUP BY c.table_schema, c.table_name
          LOOP
            EXECUTE format('ALTER TABLE %I.%I ENABLE ROW LEVEL SECURITY', item.table_schema, item.table_name);
            EXECUTE format('ALTER TABLE %I.%I FORCE ROW LEVEL SECURITY', item.table_schema, item.table_name);
            IF EXISTS (
              SELECT 1 FROM pg_policies p
              WHERE p.schemaname=item.table_schema AND p.tablename=item.table_name
                AND p.policyname='tenant_isolation'
            ) THEN
              EXECUTE format(
                'ALTER POLICY tenant_isolation ON %I.%I TO lsa_app, lsa_auth '
                'USING (tenant_id = NULLIF(current_setting(''app.tenant_id'', true), '''')::uuid) '
                'WITH CHECK (tenant_id = NULLIF(current_setting(''app.tenant_id'', true), '''')::uuid)',
                item.table_schema, item.table_name
              );
            ELSE
              EXECUTE format(
                'CREATE POLICY tenant_isolation ON %I.%I FOR ALL TO lsa_app, lsa_auth '
                'USING (tenant_id = NULLIF(current_setting(''app.tenant_id'', true), '''')::uuid) '
                'WITH CHECK (tenant_id = NULLIF(current_setting(''app.tenant_id'', true), '''')::uuid)',
                item.table_schema, item.table_name
              );
            END IF;
          END LOOP;
        END $$;
        """
    )
    policy_file = Path(__file__).resolve().parents[2] / "policies" / "row_level_security.sql"
    op.execute(policy_file.read_text(encoding="utf-8"))


def downgrade() -> None:
    bind = op.get_bind()
    for table in reversed(NEW_TABLES):
        table.drop(bind=bind, checkfirst=True)
