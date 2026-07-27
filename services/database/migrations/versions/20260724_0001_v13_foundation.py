"""Create the Lecturer Support Agent v1.3 physical data foundation.

Revision ID: 20260724_0001
Revises: None
"""
from __future__ import annotations

from pathlib import Path
from typing import Sequence

from alembic import op

from services.database.models import Base

revision: str = "20260724_0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SCHEMAS = (
    "tenant", "iam", "academic", "ingestion", "content", "conversation",
    "ai", "source", "review", "audit", "privacy",
)


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")
    op.execute(
        """
        DO $$ BEGIN
          IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'lsa_app') THEN
            CREATE ROLE lsa_app NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOBYPASSRLS;
          END IF;
          IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'lsa_auth') THEN
            CREATE ROLE lsa_auth NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOBYPASSRLS;
          END IF;
        END $$;
        """
    )
    for schema in SCHEMAS:
        op.execute(f'CREATE SCHEMA IF NOT EXISTS "{schema}"')

    bind = op.get_bind()
    Base.metadata.create_all(bind=bind, checkfirst=True)

    op.execute(
        """
        DO $$
        DECLARE schema_name text;
        BEGIN
          IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'lsa_app') THEN
            FOREACH schema_name IN ARRAY ARRAY[
              'tenant','iam','academic','ingestion','content','conversation',
              'ai','source','review','audit','privacy'
            ] LOOP
              EXECUTE format('GRANT USAGE ON SCHEMA %I TO lsa_app', schema_name);
              EXECUTE format('GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA %I TO lsa_app', schema_name);
              EXECUTE format('GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA %I TO lsa_app', schema_name);
              EXECUTE format('ALTER DEFAULT PRIVILEGES IN SCHEMA %I GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO lsa_app', schema_name);
              EXECUTE format('ALTER DEFAULT PRIVILEGES IN SCHEMA %I GRANT USAGE, SELECT ON SEQUENCES TO lsa_app', schema_name);
            END LOOP;
          END IF;
        END $$;
        """
    )

    # Apply RLS and restrictive revokes after broad schema grants so the final
    # runtime privileges are fail-closed.
    policy_file = Path(__file__).resolve().parents[2] / "policies" / "row_level_security.sql"
    op.execute(policy_file.read_text(encoding="utf-8"))


def downgrade() -> None:
    bind = op.get_bind()
    Base.metadata.drop_all(bind=bind, checkfirst=True)
    for schema in reversed(SCHEMAS):
        op.execute(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE')
