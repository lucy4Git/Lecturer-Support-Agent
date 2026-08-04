"""Convert migration-created PostgreSQL roles into least-privilege login roles.

Designed for Neon or another managed PostgreSQL service where the migration role
has CREATEROLE. Passwords are read only from environment variables and are never
printed. Run after Alembic has created the role catalogue.
"""
from __future__ import annotations

import os
from urllib.parse import urlsplit, urlunsplit

import psycopg
from psycopg import sql


def _psycopg_url(value: str) -> str:
    return value.replace("postgresql+psycopg://", "postgresql://", 1)


def _required(name: str) -> str:
    value = os.getenv(name, "")
    if not value:
        raise SystemExit(f"Required environment variable {name} is not configured.")
    return value


def main() -> None:
    url = _psycopg_url(_required("MIGRATION_DATABASE_URL"))
    credentials = {
        "lsa_app": _required("POSTGRES_APP_PASSWORD"),
        "lsa_auth": _required("POSTGRES_AUTH_PASSWORD"),
        "lsa_worker": _required("POSTGRES_WORKER_PASSWORD"),
    }
    with psycopg.connect(url, autocommit=True) as connection:
        for role, password in credentials.items():
            connection.execute(
                sql.SQL(
                    "ALTER ROLE {} LOGIN PASSWORD {} NOSUPERUSER NOCREATEDB "
                    "NOCREATEROLE NOINHERIT NOBYPASSRLS"
                ).format(sql.Identifier(role), sql.Literal(password))
            )
    print("Configured three least-privilege runtime database login roles.")


if __name__ == "__main__":
    main()
