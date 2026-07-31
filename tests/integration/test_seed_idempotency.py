from __future__ import annotations

import os

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

pytestmark = pytest.mark.integration


def _migration_url() -> str:
    return os.getenv("MIGRATION_DATABASE_URL", "")


def test_seed_is_idempotent() -> None:
    url = _migration_url()
    if not url:
        pytest.skip("MIGRATION_DATABASE_URL is not configured")

    from services.database.seeds.seed_foundation import seed_catalogue, seed_tenant

    engine = create_engine(url)
    try:
        with Session(engine) as s, s.begin():
            s.execute(text("SELECT 1 FROM iam.roles LIMIT 1"))
    except Exception as exc:
        pytest.skip(f"Database not reachable or not migrated: {exc}")

    # Run twice — second run must not raise and counts must stay the same.
    for run in range(2):
        with Session(engine) as session, session.begin():
            seed_catalogue(session)
            seed_tenant(
                session,
                "demo-north",
                "North Demonstration University",
                "ZA",
                demo_password="Idempotency!Test2026",
            )
            if run == 0:
                with Session(engine) as s2:
                    north_id = s2.execute(
                        text("SELECT id FROM tenant.institutions WHERE slug = 'demo-north'")
                    ).scalar_one()
                    count_before = s2.execute(
                        text("SELECT count(*) FROM iam.memberships WHERE tenant_id = :t"),
                        {"t": north_id},
                    ).scalar_one()
            else:
                with Session(engine) as s3:
                    count_after = s3.execute(
                        text("SELECT count(*) FROM iam.memberships WHERE tenant_id = :t"),
                        {"t": north_id},
                    ).scalar_one()
                    assert count_before == count_after, (
                        f"Seed is not idempotent: memberships changed from "
                        f"{count_before} to {count_after} on second run"
                    )

    engine.dispose()
