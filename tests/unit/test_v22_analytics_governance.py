from __future__ import annotations

import json
from datetime import date
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

import pytest

from services.api.app.ai.contracts import PrivacyClass
from services.api.app.ai.router import ModelRouter
from services.api.app.core.settings import Settings
from services.api.app.schemas.analytics import PlatformSettingUpsert
from services.api.app.services.commercial_analytics import (
    evaluate_usage_policy,
    month_bounds,
    period_bounds,
    resolve_analytics_scope,
    validate_setting_key_and_value,
)
from services.api.app.services.workspace import navigation_for_role
from services.database.models import AIUsagePolicy, Base

ROOT = Path(__file__).resolve().parents[2]


def test_v22_registers_analytics_governance_tables() -> None:
    tables = set(Base.metadata.tables)
    assert len(tables) >= 98
    assert {
        "governance.platform_settings",
        "governance.ai_usage_policies",
        "analytics.ai_usage_daily",
        "analytics.analytics_snapshots",
        "analytics.report_definitions",
        "analytics.report_runs",
        "analytics.insight_alerts",
        "audit.audit_export_jobs",
    }.issubset(tables)


def test_role_scope_resolution_fails_closed() -> None:
    user_id = uuid4()
    unit_id = uuid4()
    assert resolve_analytics_scope("lecturer", "institution", None, user_id).scope_type == "user"
    assert resolve_analytics_scope("institution_administrator", None, None, user_id).scope_type == "institution"
    assert resolve_analytics_scope("head_of_department", "organisational_unit", unit_id, user_id).scope_id == unit_id
    with pytest.raises(ValueError):
        resolve_analytics_scope("head_of_department", "institution", None, user_id)
    with pytest.raises(ValueError):
        resolve_analytics_scope("unknown_role", None, None, user_id)


def test_period_helpers_are_deterministic_and_bounded() -> None:
    assert month_bounds(date(2026, 2, 12)) == (date(2026, 2, 1), date(2026, 2, 28))
    assert period_bounds(7, date(2026, 7, 26)) == (date(2026, 7, 20), date(2026, 7, 26))
    with pytest.raises(ValueError):
        period_bounds(0)
    with pytest.raises(ValueError):
        period_bounds(367)


def test_platform_setting_rejects_live_secrets_but_accepts_reference() -> None:
    with pytest.raises(ValueError):
        validate_setting_key_and_value(
            "ai",
            "openai_api_key",
            PlatformSettingUpsert(value={"value": "".join(["s", "k", "-", "synthetic-secret-shaped-value"])}),
        )
    is_reference, value = validate_setting_key_and_value(
        "ai",
        "openai_api_key",
        PlatformSettingUpsert(
            value={"environment_variable": "OPENAI_API_KEY"},
            value_type="secret_reference",
        ),
    )
    assert is_reference
    assert value == {"environment_variable": "OPENAI_API_KEY"}


def test_ai_usage_policy_enforces_local_privacy_and_hard_limit() -> None:
    policy = AIUsagePolicy(
        id=uuid4(),
        tenant_id=uuid4(),
        name="Institution policy",
        scope_type="institution",
        scope_id=None,
        allowed_providers=["openai", "anthropic", "ollama"],
        denied_providers=[],
        local_only_privacy_classes=["confidential", "restricted_assessment"],
        source_required_for_tasks=["examination"],
        monthly_request_limit=100,
        monthly_input_token_limit=None,
        monthly_output_token_limit=None,
        monthly_cost_limit=Decimal("50.00"),
        currency_code="GBP",
        warning_threshold_percent=80,
        hard_limit_enabled=True,
        is_active=True,
        policy_metadata={},
        created_by_user_id=uuid4(),
    )
    decision = evaluate_usage_policy(
        policy=policy,
        privacy_classification="restricted_assessment",
        task_type="examination",
        usage={"request_count": 100, "input_tokens": 0, "output_tokens": 0, "estimated_cost": Decimal("10")},
    )
    assert decision.local_only
    assert decision.allowed_providers == ("ollama",)
    assert decision.source_required
    assert decision.hard_blocked
    assert "request_count_limit_reached" in decision.warning_codes


def test_model_router_applies_governed_allow_and_deny_lists() -> None:
    settings = Settings(
        _env_file=None,
        ai_enable_development_mock=False,
        ai_default_provider="auto",
        ai_fallback_order="ollama,anthropic,openai,google_gemini,deepseek",
    )
    router = ModelRouter(settings, providers={"ollama": object(), "openai": object()})
    names = router.candidate_names(
        PrivacyClass.INTERNAL,
        allowed_providers={"ollama", "openai"},
        denied_providers={"openai"},
    )
    assert names == ["ollama"]


def test_v22_navigation_is_role_specific_without_separate_applications() -> None:
    admin_keys = [item["key"] for item in navigation_for_role("institution_administrator")["items"]]
    hod_keys = [item["key"] for item in navigation_for_role("head_of_department")["items"]]
    lecturer_keys = [item["key"] for item in navigation_for_role("lecturer")["items"]]
    external_keys = [item["key"] for item in navigation_for_role("external_reviewer")["items"]]
    assert {"insights", "reports", "audit", "settings"}.issubset(admin_keys)
    assert "insights" in hod_keys and "reports" in hod_keys and "audit" not in hod_keys
    assert "insights" in lecturer_keys and "reports" in lecturer_keys
    assert "insights" in external_keys and "reports" not in external_keys
    assert admin_keys[0] == "conversation"


def test_v22_permissions_keep_audit_and_settings_admin_only() -> None:
    catalogue = json.loads((ROOT / "services/database/seeds/role_permissions.json").read_text(encoding="utf-8"))
    roles = {item["code"]: set(item["permissions"]) for item in catalogue["roles"]}
    assert {"audit.centre.read", "audit.export", "settings.manage", "ai_governance.manage"}.issubset(roles["institution_administrator"])
    assert "audit.centre.read" not in roles["head_of_department"]
    assert "settings.manage" not in roles["head_of_department"]
    assert "analytics.read_department" in roles["head_of_department"]
    assert "analytics.read_own" in roles["lecturer"]


def test_v22_migration_and_rls_cover_analytics_schema() -> None:
    migration = (ROOT / "services/database/migrations/versions/20260726_0008_v22_analytics_governance.py").read_text(encoding="utf-8")
    rls = (ROOT / "services/database/policies/row_level_security.sql").read_text(encoding="utf-8")
    assert 'CREATE SCHEMA IF NOT EXISTS "analytics"' in migration
    assert "AIUsagePolicy.__table__" in migration
    assert "AnalyticsSnapshot.__table__" in migration
    assert "row_level_security.sql" in migration
    assert "'analytics'" in rls


def test_v22_frontend_keeps_commercial_controls_in_unified_shell() -> None:
    shell = (ROOT / "apps/web/src/components/workspace-shell.tsx").read_text(encoding="utf-8")
    panels = (ROOT / "apps/web/src/components/commercial-governance-panels.tsx").read_text(encoding="utf-8")
    for label in ["Insights", "Reports", "Audit centre", "Platform settings"]:
        assert label in shell or label in panels
    for token in ["InsightsPanel", "ReportsPanel", "AuditPanel", "SettingsPanel"]:
        assert token in panels
    assert "separate artifact workspace" not in (shell + panels).lower()
