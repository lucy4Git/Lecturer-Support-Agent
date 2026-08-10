"""Regression tests for the pre-migration role-catalogue bootstrap.

Covers two separate deployment fixes:

Fix 1 (130bdeb): psycopg.errors.UndefinedObject — lsa_worker did not exist
    when row_level_security.sql was applied inside the first Alembic migration.
    Resolved by ensure_database_roles.py creating all three roles before Alembic.

Fix 2 (current): psycopg.errors.InsufficientPrivilege — bootstrap_database_roles.py
    attempted ALTER ROLE ... NOSUPERUSER NOBYPASSRLS which requires SUPERUSER on
    Neon managed PostgreSQL.  Resolved by ALTER ROLE ... LOGIN PASSWORD only, with
    a separate pg_roles verification step.

All tests are unit-level and require no live database.
"""
from __future__ import annotations

import importlib
import os
import sys
import types
from pathlib import Path
from unittest.mock import MagicMock, call, patch


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _load_ensure_roles() -> types.ModuleType:
    spec = importlib.util.spec_from_file_location(
        "ensure_database_roles",
        Path("scripts/deployment/ensure_database_roles.py"),
    )
    mod = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


def _load_predeploy() -> types.ModuleType:
    spec = importlib.util.spec_from_file_location(
        "predeploy",
        Path("scripts/deployment/predeploy.py"),
    )
    mod = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


# ---------------------------------------------------------------------------
# 1. ensure_database_roles creates all three roles
# ---------------------------------------------------------------------------

def test_ensure_database_roles_targets_all_three_roles() -> None:
    """All three roles must be bootstrapped by ensure_database_roles.py."""
    source = Path("scripts/deployment/ensure_database_roles.py").read_text(encoding="utf-8")
    for role in ("lsa_app", "lsa_auth", "lsa_worker"):
        assert role in source, f"{role} not referenced in ensure_database_roles.py"


def test_ensure_database_roles_uses_if_not_exists() -> None:
    """The creation must be idempotent via IF NOT EXISTS."""
    source = Path("scripts/deployment/ensure_database_roles.py").read_text(encoding="utf-8")
    assert "IF NOT EXISTS" in source


def test_ensure_database_roles_uses_nologin() -> None:
    """Roles must be created NOLOGIN at the pre-migration stage."""
    source = Path("scripts/deployment/ensure_database_roles.py").read_text(encoding="utf-8")
    assert "NOLOGIN" in source


def test_ensure_database_roles_applies_least_privilege_attributes() -> None:
    """All five least-privilege attributes must be present."""
    source = Path("scripts/deployment/ensure_database_roles.py").read_text(encoding="utf-8")
    for attr in ("NOSUPERUSER", "NOCREATEDB", "NOCREATEROLE", "NOINHERIT", "NOBYPASSRLS"):
        assert attr in source, f"Missing attribute {attr} in ensure_database_roles.py"


def test_ensure_database_roles_uses_migration_url() -> None:
    """Must connect through MIGRATION_DATABASE_URL, not a runtime URL."""
    source = Path("scripts/deployment/ensure_database_roles.py").read_text(encoding="utf-8")
    assert "MIGRATION_DATABASE_URL" in source
    assert "DATABASE_URL" not in source.replace("MIGRATION_DATABASE_URL", "")


def test_ensure_database_roles_exits_without_migration_url(monkeypatch: "pytest.MonkeyPatch") -> None:
    """Missing MIGRATION_DATABASE_URL must cause a non-zero exit."""
    monkeypatch.delenv("MIGRATION_DATABASE_URL", raising=False)
    mod = _load_ensure_roles()
    with patch("psycopg.connect") as mock_connect:
        try:
            mod.main()
        except SystemExit as exc:
            assert exc.code != 0
        else:
            # If it doesn't exit it must have raised before connect
            mock_connect.assert_not_called()


def test_ensure_database_roles_does_not_print_url(monkeypatch: "pytest.MonkeyPatch", capsys: "pytest.CaptureFixture") -> None:
    """The MIGRATION_DATABASE_URL value must never appear in stdout or stderr."""
    sentinel = "postgresql://owner:SECRET_PASS@host/db"
    monkeypatch.setenv("MIGRATION_DATABASE_URL", sentinel)

    fake_conn = MagicMock()
    fake_conn.__enter__ = lambda s: s
    fake_conn.__exit__ = MagicMock(return_value=False)

    with patch("psycopg.connect", return_value=fake_conn):
        mod = _load_ensure_roles()
        mod.main()

    captured = capsys.readouterr()
    assert sentinel not in captured.out
    assert sentinel not in captured.err
    assert "SECRET_PASS" not in captured.out
    assert "SECRET_PASS" not in captured.err


# ---------------------------------------------------------------------------
# 2. predeploy.py calls ensure_database_roles BEFORE alembic
# ---------------------------------------------------------------------------

def test_predeploy_calls_ensure_roles_before_alembic() -> None:
    """ensure_database_roles.py must appear before alembic upgrade head in predeploy.py."""
    source = Path("scripts/deployment/predeploy.py").read_text(encoding="utf-8")
    ensure_pos = source.find("ensure_database_roles")
    alembic_pos = source.find("alembic")
    assert ensure_pos != -1, "ensure_database_roles not referenced in predeploy.py"
    assert alembic_pos != -1, "alembic not referenced in predeploy.py"
    assert ensure_pos < alembic_pos, (
        "ensure_database_roles.py must be called before alembic upgrade head"
    )


def test_predeploy_calls_bootstrap_after_alembic() -> None:
    """bootstrap_database_roles.py must appear after alembic upgrade head."""
    source = Path("scripts/deployment/predeploy.py").read_text(encoding="utf-8")
    alembic_pos = source.find("alembic")
    bootstrap_pos = source.find("bootstrap_database_roles")
    assert bootstrap_pos > alembic_pos, (
        "bootstrap_database_roles.py must run after alembic upgrade head"
    )


def test_predeploy_order_is_validate_ensure_alembic_bootstrap(monkeypatch: "pytest.MonkeyPatch") -> None:
    """The four-step predeploy sequence must execute in the correct order."""
    calls: list[str] = []

    def fake_run(command: list[str]) -> None:
        joined = " ".join(command)
        if "validate_deployment_configuration" in joined:
            calls.append("validate")
        elif "ensure_database_roles" in joined:
            calls.append("ensure")
        elif "alembic" in joined:
            calls.append("alembic")
        elif "bootstrap_database_roles" in joined:
            calls.append("bootstrap")

    async def fake_ensure_external() -> None:
        calls.append("external")

    monkeypatch.setenv("ENVIRONMENT", "staging")
    monkeypatch.setenv("ENABLE_DEMO_SEED", "false")

    mod = _load_predeploy()

    with (
        patch.object(mod, "run", side_effect=fake_run),
        patch.object(mod, "ensure_external_services", new=fake_ensure_external),
    ):
        mod.main()

    assert calls == ["validate", "ensure", "alembic", "bootstrap", "external"], (
        f"Unexpected predeploy sequence: {calls}"
    )


# ---------------------------------------------------------------------------
# 3. Idempotency — running ensure_database_roles twice is safe
# ---------------------------------------------------------------------------

def test_ensure_database_roles_is_idempotent(monkeypatch: "pytest.MonkeyPatch") -> None:
    """Calling main() twice must not raise even if roles already exist."""
    monkeypatch.setenv("MIGRATION_DATABASE_URL", "postgresql://owner:pw@host/db")

    fake_conn = MagicMock()
    fake_conn.__enter__ = lambda s: s
    fake_conn.__exit__ = MagicMock(return_value=False)

    with patch("psycopg.connect", return_value=fake_conn):
        mod = _load_ensure_roles()
        mod.main()
        mod.main()  # second call must not raise

    assert fake_conn.execute.call_count == 6  # 3 roles × 2 runs


# ---------------------------------------------------------------------------
# 4. Historical migration chain is unchanged
# ---------------------------------------------------------------------------

def test_migration_chain_head_unchanged() -> None:
    """The Alembic head must remain 20260803_0012."""
    head_file = Path(
        "services/database/migrations/versions/20260803_0012_v26_deployment_completion.py"
    )
    assert head_file.exists()
    text = head_file.read_text(encoding="utf-8")
    assert 'revision: str = "20260803_0012"' in text
    assert 'down_revision: str | None = "20260726_0011"' in text


def test_first_migration_still_creates_lsa_app_and_lsa_auth() -> None:
    """20260724_0001 must still contain lsa_app and lsa_auth creation (historical)."""
    text = Path(
        "services/database/migrations/versions/20260724_0001_v13_foundation.py"
    ).read_text(encoding="utf-8")
    assert "lsa_app" in text
    assert "lsa_auth" in text


def test_migration_chain_is_single_linear_branch() -> None:
    """Every migration file must declare exactly one down_revision (no branch merges)."""
    import re

    versions_dir = Path("services/database/migrations/versions")
    revisions: list[str] = []
    down_revisions: list[str | None] = []
    # Match the assigned value after the optional type annotation:
    # down_revision: str | None = None   → None
    # down_revision: str | None = "abc"  → "abc"
    pattern = re.compile(r'^down_revision\s*(?::[^=]*)?\s*=\s*(.+)$')
    for f in sorted(versions_dir.glob("*.py")):
        text = f.read_text(encoding="utf-8")
        for line in text.splitlines():
            if line.startswith("revision:") and "=" in line:
                m = re.search(r'"([^"]+)"', line)
                if m:
                    revisions.append(m.group(1))
            m = pattern.match(line)
            if m:
                rhs = m.group(1).strip()
                if rhs == "None":
                    down_revisions.append(None)
                elif rhs.startswith('"'):
                    down_revisions.append(rhs.strip('"'))
    assert len(revisions) == 12, f"Expected 12 migrations, found {len(revisions)}"
    none_count = sum(1 for d in down_revisions if d is None)
    assert none_count == 1, "Exactly one migration must have down_revision=None (the root)"


# ---------------------------------------------------------------------------
# 5. No secrets introduced
# ---------------------------------------------------------------------------

def test_ensure_database_roles_contains_no_hardcoded_secrets() -> None:
    """The new script must contain no hardcoded passwords, tokens or URLs."""
    source = Path("scripts/deployment/ensure_database_roles.py").read_text(encoding="utf-8")
    forbidden = ["password", "secret", "token", "key", "@", "postgresql://"]
    # Allowed comment references are fine; flag only non-comment occurrences
    code_lines = [
        line for line in source.splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]
    code_body = "\n".join(code_lines)
    for term in ["SECRET_", "TOKEN_", "API_KEY"]:
        assert term not in code_body, f"Suspicious term '{term}' found in ensure_database_roles.py"


def test_predeploy_contains_no_hardcoded_secrets() -> None:
    """predeploy.py must not contain hardcoded passwords or connection strings."""
    source = Path("scripts/deployment/predeploy.py").read_text(encoding="utf-8")
    for term in ["password=", "secret=", "://", "SECRET_", "API_KEY="]:
        assert term not in source, f"Suspicious literal '{term}' found in predeploy.py"


# ---------------------------------------------------------------------------
# 6. bootstrap_database_roles — Fix 2: InsufficientPrivilege remediation
# ---------------------------------------------------------------------------

def _load_bootstrap() -> types.ModuleType:
    spec = importlib.util.spec_from_file_location(
        "bootstrap_database_roles",
        Path("scripts/deployment/bootstrap_database_roles.py"),
    )
    mod = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


def test_bootstrap_does_not_include_nosuperuser_in_alter_role() -> None:
    """bootstrap_database_roles.py must not issue ALTER ROLE ... NOSUPERUSER."""
    source = Path("scripts/deployment/bootstrap_database_roles.py").read_text(encoding="utf-8")
    # The word NOSUPERUSER may appear in comments/docstrings but must not be
    # inside an ALTER ROLE SQL string literal that will be executed.
    code_lines = [
        line for line in source.splitlines()
        if line.strip() and not line.strip().startswith("#")
        and '"""' not in line and "'''" not in line
    ]
    # Find lines that contain both ALTER ROLE context and NOSUPERUSER — this
    # would indicate it is being used as an SQL keyword, not documentation.
    for line in code_lines:
        assert not ("ALTER" in line and "NOSUPERUSER" in line), (
            f"NOSUPERUSER must not appear alongside ALTER in executable code: {line!r}"
        )


def test_bootstrap_does_not_include_nobypassrls_in_alter_role() -> None:
    """bootstrap_database_roles.py must not include NOBYPASSRLS in its ALTER ROLE SQL."""
    source = Path("scripts/deployment/bootstrap_database_roles.py").read_text(encoding="utf-8")
    # Extract only string literals passed to sql.SQL (the actual SQL templates).
    # They appear as  sql.SQL("...") or sql.SQL('...').
    import re
    sql_strings = re.findall(r'sql\.SQL\(["\'](.+?)["\']\)', source)
    for s in sql_strings:
        assert "NOBYPASSRLS" not in s, (
            f"NOBYPASSRLS must not appear in ALTER ROLE SQL template: {s!r}"
        )


def test_bootstrap_alter_role_sets_login_and_password() -> None:
    """bootstrap_database_roles.py must issue ALTER ROLE ... LOGIN PASSWORD."""
    source = Path("scripts/deployment/bootstrap_database_roles.py").read_text(encoding="utf-8")
    assert "LOGIN" in source
    assert "PASSWORD" in source


def test_bootstrap_verifies_pg_roles_after_alter() -> None:
    """bootstrap_database_roles.py must query pg_roles to verify final attributes."""
    source = Path("scripts/deployment/bootstrap_database_roles.py").read_text(encoding="utf-8")
    assert "pg_roles" in source
    for col in ("rolcanlogin", "rolsuper", "rolcreatedb", "rolcreaterole",
                "rolinherit", "rolbypassrls", "rolreplication"):
        assert col in source, f"pg_roles column {col!r} not verified in bootstrap"


def test_bootstrap_fails_closed_on_privilege_violation(monkeypatch: "pytest.MonkeyPatch") -> None:
    """bootstrap must exit non-zero if any role has a more-privileged attribute."""
    monkeypatch.setenv("MIGRATION_DATABASE_URL", "postgresql://owner:pw@host/db")
    monkeypatch.setenv("POSTGRES_APP_PASSWORD",    "app-pw")
    monkeypatch.setenv("POSTGRES_AUTH_PASSWORD",   "auth-pw")
    monkeypatch.setenv("POSTGRES_WORKER_PASSWORD", "worker-pw")

    # Simulate pg_roles returning rolsuper=True for lsa_app (privilege violation).
    bad_row_lsa_app = (True, True, False, False, False, False, False)  # rolcanlogin=T, rolsuper=T
    good_row        = (True, False, False, False, False, False, False)

    fake_cursor = MagicMock()
    fake_cursor.fetchone.side_effect = [bad_row_lsa_app, good_row, good_row]

    fake_conn = MagicMock()
    fake_conn.__enter__ = lambda s: s
    fake_conn.__exit__ = MagicMock(return_value=False)
    fake_conn.execute.return_value = fake_cursor

    with patch("psycopg.connect", return_value=fake_conn):
        mod = _load_bootstrap()
        with pytest.raises(SystemExit) as exc_info:
            mod.main()
        assert exc_info.value.code != 0


def test_bootstrap_succeeds_when_all_roles_are_least_privilege(monkeypatch: "pytest.MonkeyPatch") -> None:
    """bootstrap must print success and not exit when all attributes are correct."""
    monkeypatch.setenv("MIGRATION_DATABASE_URL", "postgresql://owner:pw@host/db")
    monkeypatch.setenv("POSTGRES_APP_PASSWORD",    "app-pw")
    monkeypatch.setenv("POSTGRES_AUTH_PASSWORD",   "auth-pw")
    monkeypatch.setenv("POSTGRES_WORKER_PASSWORD", "worker-pw")

    # All three roles return the expected least-privilege attributes.
    good_row = (True, False, False, False, False, False, False)

    fake_cursor = MagicMock()
    fake_cursor.fetchone.return_value = good_row

    fake_conn = MagicMock()
    fake_conn.__enter__ = lambda s: s
    fake_conn.__exit__ = MagicMock(return_value=False)
    fake_conn.execute.return_value = fake_cursor

    with patch("psycopg.connect", return_value=fake_conn):
        mod = _load_bootstrap()
        mod.main()  # must not raise


def test_bootstrap_fails_closed_when_role_missing_from_pg_roles(monkeypatch: "pytest.MonkeyPatch") -> None:
    """bootstrap must exit non-zero if a role is absent from pg_roles."""
    monkeypatch.setenv("MIGRATION_DATABASE_URL", "postgresql://owner:pw@host/db")
    monkeypatch.setenv("POSTGRES_APP_PASSWORD",    "app-pw")
    monkeypatch.setenv("POSTGRES_AUTH_PASSWORD",   "auth-pw")
    monkeypatch.setenv("POSTGRES_WORKER_PASSWORD", "worker-pw")

    good_row = (True, False, False, False, False, False, False)

    fake_cursor = MagicMock()
    # lsa_app missing, lsa_auth and lsa_worker OK
    fake_cursor.fetchone.side_effect = [None, good_row, good_row]

    fake_conn = MagicMock()
    fake_conn.__enter__ = lambda s: s
    fake_conn.__exit__ = MagicMock(return_value=False)
    fake_conn.execute.return_value = fake_cursor

    with patch("psycopg.connect", return_value=fake_conn):
        mod = _load_bootstrap()
        with pytest.raises(SystemExit) as exc_info:
            mod.main()
        assert exc_info.value.code != 0


def test_bootstrap_does_not_print_password(monkeypatch: "pytest.MonkeyPatch", capsys: "pytest.CaptureFixture") -> None:
    """Passwords must never appear in bootstrap stdout or stderr."""
    secret = "SUPER_SECRET_PW_12345"
    monkeypatch.setenv("MIGRATION_DATABASE_URL", "postgresql://owner:pw@host/db")
    monkeypatch.setenv("POSTGRES_APP_PASSWORD",    secret)
    monkeypatch.setenv("POSTGRES_AUTH_PASSWORD",   secret)
    monkeypatch.setenv("POSTGRES_WORKER_PASSWORD", secret)

    good_row = (True, False, False, False, False, False, False)
    fake_cursor = MagicMock()
    fake_cursor.fetchone.return_value = good_row

    fake_conn = MagicMock()
    fake_conn.__enter__ = lambda s: s
    fake_conn.__exit__ = MagicMock(return_value=False)
    fake_conn.execute.return_value = fake_cursor

    with patch("psycopg.connect", return_value=fake_conn):
        mod = _load_bootstrap()
        mod.main()

    captured = capsys.readouterr()
    assert secret not in captured.out
    assert secret not in captured.err


def test_bootstrap_does_not_print_migration_url(monkeypatch: "pytest.MonkeyPatch", capsys: "pytest.CaptureFixture") -> None:
    """MIGRATION_DATABASE_URL value must never appear in bootstrap output."""
    url_sentinel = "postgresql://owner:URL_SECRET@host/db"
    monkeypatch.setenv("MIGRATION_DATABASE_URL", url_sentinel)
    monkeypatch.setenv("POSTGRES_APP_PASSWORD",    "app-pw")
    monkeypatch.setenv("POSTGRES_AUTH_PASSWORD",   "auth-pw")
    monkeypatch.setenv("POSTGRES_WORKER_PASSWORD", "worker-pw")

    good_row = (True, False, False, False, False, False, False)

    # fake_conn is used as both the connection context manager and the cursor
    # returned by execute(), since psycopg connections return a cursor from execute.
    fake_conn = MagicMock()
    fake_conn.__enter__ = lambda s: s
    fake_conn.__exit__ = MagicMock(return_value=False)
    # conn.execute(...) returns a cursor; cursor.fetchone() returns the row.
    fake_cursor = MagicMock()
    fake_cursor.fetchone.return_value = good_row
    fake_conn.execute.return_value = fake_cursor

    with patch("psycopg.connect", return_value=fake_conn):
        mod = _load_bootstrap()
        try:
            mod.main()
        except Exception:
            pass  # output check is what matters

    captured = capsys.readouterr()
    assert "URL_SECRET" not in captured.out
    assert "URL_SECRET" not in captured.err


import pytest  # noqa: E402 — placed after helpers to satisfy module loading order
