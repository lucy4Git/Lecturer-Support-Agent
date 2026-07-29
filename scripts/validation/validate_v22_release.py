from __future__ import annotations

import json
import py_compile
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

REQUIRED = [
    "services/database/models/analytics.py",
    "services/database/migrations/versions/20260726_0008_v22_analytics_governance.py",
    "services/api/app/schemas/analytics.py",
    "services/api/app/services/commercial_analytics.py",
    "services/api/app/routes/analytics.py",
    "apps/web/src/components/commercial-governance-panels.tsx",
    "tests/unit/test_v22_analytics_governance.py",
    "tests/e2e/live-preview/analytics-governance.spec.ts",
    "docs/implementation/PHASE_11_V2.2_ANALYTICS_GOVERNANCE_IMPLEMENTATION_REPORT.md",
    "docs/api/V2.2_ANALYTICS_REPORTING_GOVERNANCE_API.md",
    "docs/ux/V2.2_INSIGHTS_REPORTS_AUDIT_SETTINGS.md",
    "docs/security/V2.2_ANALYTICS_AUDIT_AND_SETTINGS_SECURITY.md",
    "docs/governance/AI_USAGE_GOVERNANCE.md",
    "docs/data/V2.2_ANALYTICS_DATA_MODEL.md",
    "docs/requirements/V2.2_ACCEPTANCE_CRITERIA.md",
    "docs/operations/V2.2_OWNER_MACHINE_VALIDATION.md",
    "docs/testing/V2.2_STATIC_VALIDATION_EVIDENCE.md",
    "docs/testing/V2.2_RELEASE_VALIDATION_REPORT.md",
    "docs/architecture/adr/ADR-016-scoped-analytics-ai-governance-and-audit-centre.md",
    "docs/architecture/uml/v2.2/README.md",
]
missing = [item for item in REQUIRED if not (ROOT / item).exists()]
if missing:
    raise SystemExit("Missing v2.2 files: " + ", ".join(missing))

for rel in [
    "services/database/models/analytics.py",
    "services/database/seeds/seed_foundation.py",
    "services/api/app/schemas/analytics.py",
    "services/api/app/services/commercial_analytics.py",
    "services/api/app/routes/analytics.py",
    "scripts/validation/validate_v22_release.py",
]:
    py_compile.compile(str(ROOT / rel), doraise=True)

from services.api.app.main import app
from services.database.models import Base

assert tuple(map(int, app.version.split("."))) >= (2, 2, 0)
assert len(Base.metadata.tables) >= 98
required_tables = {
    "governance.platform_settings",
    "governance.ai_usage_policies",
    "analytics.ai_usage_daily",
    "analytics.analytics_snapshots",
    "analytics.report_definitions",
    "analytics.report_runs",
    "analytics.insight_alerts",
    "audit.audit_export_jobs",
}
assert required_tables <= set(Base.metadata.tables)

paths = set(app.openapi()["paths"].keys())
for path in [
    "/api/v1/analytics/overview",
    "/api/v1/analytics/ai-usage",
    "/api/v1/analytics/report-definitions",
    "/api/v1/analytics/report-runs",
    "/api/v1/analytics/alerts",
    "/api/v1/ai-governance/policies",
    "/api/v1/audit-centre/events",
    "/api/v1/audit-centre/security-events",
    "/api/v1/audit-centre/exports",
    "/api/v1/platform-settings",
    "/api/v1/platform-settings/{category}/{setting_key}",
]:
    assert path in paths, path

catalogue = json.loads((ROOT / "services/database/seeds/role_permissions.json").read_text(encoding="utf-8"))
permission_codes = {item["code"] for item in catalogue["permissions"]}
required_permissions = {
    "analytics.read_own",
    "analytics.read_department",
    "analytics.read_institution",
    "reports.generate",
    "reports.manage",
    "ai_governance.read",
    "ai_governance.manage",
    "audit.centre.read",
    "audit.export",
    "settings.read",
    "settings.manage",
}
assert required_permissions <= permission_codes
roles = {item["code"]: set(item["permissions"]) for item in catalogue["roles"]}
assert {"audit.centre.read", "audit.export", "settings.manage", "ai_governance.manage"} <= roles["institution_administrator"]
assert "audit.centre.read" not in roles["head_of_department"]
assert "settings.manage" not in roles["head_of_department"]
assert "analytics.read_department" in roles["head_of_department"]
assert "analytics.read_own" in roles["lecturer"]

migration = (ROOT / "services/database/migrations/versions/20260726_0008_v22_analytics_governance.py").read_text(encoding="utf-8")
rls = (ROOT / "services/database/policies/row_level_security.sql").read_text(encoding="utf-8")
assert 'CREATE SCHEMA IF NOT EXISTS "analytics"' in migration
assert "row_level_security.sql" in migration
assert "'analytics'" in rls

web_package = json.loads((ROOT / "apps/web/package.json").read_text(encoding="utf-8"))
assert tuple(map(int, web_package["version"].split("."))) >= (2, 2, 0)
assert 'version = "2.' in (ROOT / "pyproject.toml").read_text(encoding="utf-8")
shell = (ROOT / "apps/web/src/components/workspace-shell.tsx").read_text(encoding="utf-8")
panels = (ROOT / "apps/web/src/components/commercial-governance-panels.tsx").read_text(encoding="utf-8")
for label in ["Insights", "Reports", "Audit centre", "Platform settings"]:
    assert label in shell or label in panels
for token in ["InsightsPanel", "ReportsPanel", "AuditPanel", "SettingsPanel"]:
    assert token in panels

uml_files = list((ROOT / "docs/architecture/uml/v2.2").glob("*.puml"))
assert len(uml_files) == 7
for file in uml_files:
    text = file.read_text(encoding="utf-8")
    assert text.lstrip().startswith("@startuml") and text.rstrip().endswith("@enduml"), file

print(
    "v2.2 release validation passed: scoped analytics, immutable reports, AI usage governance, "
    "admin-only Audit Centre, versioned non-secret settings, unified commercial panels, security "
    "controls, documentation, diagrams, and version metadata are present."
)
