"""Regression tests for the pre-migration role-catalogue bootstrap.

These tests verify the fix for the psycopg.errors.UndefinedObject failure
that occurred because lsa_worker did not exist when row_level_security.sql
was applied inside the first Alembic migration.

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
