from __future__ import annotations

import os

import psycopg
from psycopg import sql


def required(name: str) -> str:
    value = os.getenv(name, "")
    if not value:
        raise SystemExit(f"{name} is required to provision database roles.")
    return value


def main() -> None:
    owner_url = required("MIGRATION_DATABASE_URL").replace("+psycopg", "")
    passwords = {
        "lsa_app": required("POSTGRES_APP_PASSWORD"),
        "lsa_auth": required("POSTGRES_AUTH_PASSWORD"),
        "lsa_worker": required("POSTGRES_WORKER_PASSWORD"),
    }
    database_name = os.getenv("POSTGRES_DB", "lecturer_support_agent")
    with psycopg.connect(owner_url, autocommit=True) as connection:
        with connection.cursor() as cursor:
            for role, password in passwords.items():
                cursor.execute("SELECT 1 FROM pg_roles WHERE rolname = %s", (role,))
                if cursor.fetchone() is None:
                    cursor.execute(
                        sql.SQL("CREATE ROLE {} LOGIN PASSWORD {}").format(
                            sql.Identifier(role), sql.Literal(password)
                        )
                    )
                else:
                    cursor.execute(
                        sql.SQL("ALTER ROLE {} LOGIN PASSWORD {}").format(
                            sql.Identifier(role), sql.Literal(password)
                        )
                    )
                cursor.execute(
                    sql.SQL(
                        "ALTER ROLE {} NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOBYPASSRLS"
                    ).format(sql.Identifier(role))
                )
            cursor.execute(
                sql.SQL("GRANT CONNECT ON DATABASE {} TO lsa_app, lsa_auth, lsa_worker").format(
                    sql.Identifier(database_name)
                )
            )
    print("Database application, authentication, and worker roles are provisioned.")


if __name__ == "__main__":
    main()
