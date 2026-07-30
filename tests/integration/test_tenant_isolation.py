from __future__ import annotations

import os
from uuid import NAMESPACE_URL, uuid5

import pytest

psycopg = pytest.importorskip("psycopg")

pytestmark = [pytest.mark.integration, pytest.mark.security]


def stable_id(value: str):
    return uuid5(NAMESPACE_URL, f"lecturer-support-agent:{value}")


def application_url() -> str:
    url = os.getenv("DATABASE_URL", "")
    return url.replace("postgresql+psycopg://", "postgresql://")


def test_rls_blocks_cross_tenant_reads_and_writes() -> None:
    url = application_url()
    if not url:
        pytest.skip("DATABASE_URL is not configured")
    try:
        connection = psycopg.connect(url)
    except psycopg.OperationalError as exc:
        pytest.skip(f"PostgreSQL is not reachable: {exc}")

    north = stable_id("tenant:demo-north")
    south = stable_id("tenant:demo-south")
    with connection:
        with connection.cursor() as cursor:
            cursor.execute("SELECT set_config('app.tenant_id', %s, true)", (str(north),))
            cursor.execute("SELECT count(*) FROM iam.memberships")
            assert cursor.fetchone()[0] == 8
            cursor.execute("SELECT count(*) FROM iam.memberships WHERE tenant_id = %s", (south,))
            assert cursor.fetchone()[0] == 0

            with pytest.raises(psycopg.errors.InsufficientPrivilege):
                cursor.execute(
                    "INSERT INTO tenant.settings (id, tenant_id, setting_key, setting_value, is_secret_reference) "
                    "VALUES (gen_random_uuid(), %s, 'cross_tenant_attempt', '{}'::jsonb, false)",
                    (south,),
                )
    connection.close()
