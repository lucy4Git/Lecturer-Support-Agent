"""Convert pre-migration placeholder roles into least-privilege LOGIN roles.

Designed for Neon or another managed PostgreSQL service where the migration
role has CREATEROLE but is NOT a true superuser.

The roles lsa_app, lsa_auth and lsa_worker were already created by
ensure_database_roles.py with the correct least-privilege attributes:

    NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOBYPASSRLS

This step performs ONLY the operations needed to activate them for runtime
use:

    ALTER ROLE <role> LOGIN PASSWORD <env-password>;

Attempting to re-declare privileged attributes such as NOSUPERUSER or
NOBYPASSRLS on ALTER ROLE requires the caller to hold SUPERUSER, which
Neon does not grant to migration owners and is not required here because
those attributes are already set.

After conversion, this script reads pg_roles and verifies that every role
has EXACTLY the expected least-privilege state.  Deployment fails closed if
any attribute is more permissive than required.

Passwords are read only from environment variables and are never printed.
Executed over MIGRATION_DATABASE_URL (direct, non-pooled, owner account).
"""
from __future__ import annotations

import os
import sys
from dataclasses import dataclass

import psycopg
from psycopg import sql


_ROLES = ("lsa_app", "lsa_auth", "lsa_worker")

# Expected final pg_roles attribute values for every runtime role.
# Any deviation causes a non-zero exit — fail closed.
_EXPECTED = {
    "rolcanlogin":   True,
    "rolsuper":      False,
    "rolcreatedb":   False,
    "rolcreaterole": False,
    "rolinherit":    False,
    "rolbypassrls":  False,
    "rolreplication":False,
}


def _psycopg_url(value: str) -> str:
    return value.replace("postgresql+psycopg://", "postgresql://", 1)


def _required(name: str) -> str:
    value = os.getenv(name, "")
    if not value:
        print(f"ERROR: Required environment variable {name} is not configured.", file=sys.stderr)
        sys.exit(1)
    return value


def main() -> None:
    url = _psycopg_url(_required("MIGRATION_DATABASE_URL"))
    credentials = {
        "lsa_app":    _required("POSTGRES_APP_PASSWORD"),
        "lsa_auth":   _required("POSTGRES_AUTH_PASSWORD"),
        "lsa_worker": _required("POSTGRES_WORKER_PASSWORD"),
    }

    with psycopg.connect(url, autocommit=True) as conn:
        # Step 1 — grant LOGIN and set password only.
        # The secure least-privilege attributes (NOSUPERUSER, NOCREATEDB,
        # NOCREATEROLE, NOINHERIT, NOBYPASSRLS) were established during CREATE
        # ROLE in ensure_database_roles.py.  Re-declaring them here would
        # require SUPERUSER, which Neon does not grant to migration owners.
        for role, password in credentials.items():
            conn.execute(
                sql.SQL("ALTER ROLE {} LOGIN PASSWORD {}").format(
                    sql.Identifier(role),
                    sql.Literal(password),
                )
            )

        # Step 2 — verify the final role catalogue.
        columns = list(_EXPECTED.keys())
        col_sql = sql.SQL(", ").join(sql.Identifier(c) for c in columns)
        violations: list[str] = []

        for role in _ROLES:
            row = conn.execute(
                sql.SQL("SELECT {} FROM pg_roles WHERE rolname = {}").format(
                    col_sql,
                    sql.Literal(role),
                )
            ).fetchone()

            if row is None:
                violations.append(f"{role}: role not found in pg_roles")
                continue

            for col, expected in _EXPECTED.items():
                actual = row[columns.index(col)]
                if actual != expected:
                    violations.append(
                        f"{role}.{col}: expected {expected}, got {actual}"
                    )

    if violations:
        print("FATAL: role attribute verification failed:", file=sys.stderr)
        for v in violations:
            print(f"  {v}", file=sys.stderr)
        sys.exit(1)

    print(
        f"Bootstrap complete: {', '.join(_ROLES)} configured as "
        "least-privilege LOGIN roles and verified."
    )


if __name__ == "__main__":
    main()
