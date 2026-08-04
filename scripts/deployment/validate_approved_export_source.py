"""Fail closed unless the source database contains only approved tenant data.

This preflight does not export content and never prints the database URL.  It is
required before ``Export-ApprovedLocalData.ps1`` because pg_dump does not support
row-level tenant filters.  Use it against a dedicated, reviewed local migration
source database—not a mixed or production database.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

import psycopg


def _plain_url(value: str) -> str:
    return value.replace("postgresql+psycopg://", "postgresql://", 1)


def main() -> None:
    if os.getenv("EXPORT_SOURCE_APPROVED", "").lower() not in {"1", "true", "yes"}:
        raise SystemExit(
            "Set EXPORT_SOURCE_APPROVED=true only after the data owner has approved "
            "this dedicated migration source database."
        )
    environment = os.getenv("ENVIRONMENT", "development").lower()
    if environment == "production":
        raise SystemExit("A production database cannot be used as the local export source.")
    raw_url = os.getenv("MIGRATION_DATABASE_URL", "")
    if not raw_url:
        raise SystemExit("MIGRATION_DATABASE_URL is required.")
    approved = {
        value.strip().lower()
        for value in os.getenv("APPROVED_TENANT_IDS", "").split(",")
        if value.strip()
    }
    if not approved:
        raise SystemExit("APPROVED_TENANT_IDS must contain every approved institution UUID.")

    with psycopg.connect(_plain_url(raw_url)) as connection:
        institutions = connection.execute(
            "SELECT id::text, slug, display_name FROM tenant.institutions ORDER BY id"
        ).fetchall()
        revision_row = connection.execute("SELECT version_num FROM alembic_version").fetchone()
    actual = {str(row[0]).lower() for row in institutions}
    unapproved = actual - approved
    missing = approved - actual
    if unapproved:
        raise SystemExit(
            "Export refused: source database contains unapproved tenant IDs: "
            + ", ".join(sorted(unapproved))
        )
    if missing:
        raise SystemExit(
            "Export refused: approved tenant IDs are absent from the source database: "
            + ", ".join(sorted(missing))
        )

    output = Path(os.getenv("APPROVED_SOURCE_PREFLIGHT_OUTPUT", "runtime/deployment/approved-source.json"))
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(
            {
                "schema_version": "1.0",
                "environment": environment,
                "alembic_revision": revision_row[0] if revision_row else None,
                "approved_tenants": [
                    {"id": str(row[0]), "slug": row[1], "display_name": row[2]}
                    for row in institutions
                ],
                "source_contains_only_approved_tenants": True,
                "content_exported": False,
            },
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    print(f"Approved export-source preflight passed for {len(institutions)} tenant(s).")


if __name__ == "__main__":
    main()
