"""Idempotent pre-migration role catalogue bootstrap.

Creates the three least-privilege PostgreSQL roles required by the
row_level_security.sql policy as NOLOGIN placeholder roles BEFORE
Alembic runs.  The subsequent bootstrap_database_roles.py step
converts them to LOGIN roles using the environment passwords.

Safe properties:
- NOLOGIN       — cannot authenticate at this stage
- NOSUPERUSER   — no elevated privileges
- NOCREATEDB    — cannot create databases
- NOCREATEROLE  — cannot create or alter other roles
- NOINHERIT     — no inherited privileges
- NOBYPASSRLS   — subject to row-level security

Idempotent: uses IF NOT EXISTS so re-running is safe.
Executed over MIGRATION_DATABASE_URL (direct, non-pooled, owner account).
No secret values are printed.
"""
from __future__ import annotations

import os
import sys

import psycopg
from psycopg import sql


_ROLES = ("lsa_app", "lsa_auth", "lsa_worker")
_ATTRS = "NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOBYPASSRLS"


def _psycopg_url(value: str) -> str:
    return value.replace("postgresql+psycopg://", "postgresql://", 1)


def main() -> None:
    raw = os.getenv("MIGRATION_DATABASE_URL", "")
    if not raw:
        print("ERROR: MIGRATION_DATABASE_URL is not configured.", file=sys.stderr)
        sys.exit(1)

    url = _psycopg_url(raw)
    with psycopg.connect(url, autocommit=True) as conn:
        for role in _ROLES:
            conn.execute(
                sql.SQL(
                    "DO $$ BEGIN "
                    "  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = {role}) THEN "
                    "    CREATE ROLE {ident} " + _ATTRS + "; "
                    "  END IF; "
                    "END $$"
                ).format(
                    role=sql.Literal(role),
                    ident=sql.Identifier(role),
                )
            )
    print(f"Pre-migration role catalogue: {', '.join(_ROLES)} confirmed.")


if __name__ == "__main__":
    main()
