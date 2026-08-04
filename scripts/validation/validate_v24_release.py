from __future__ import annotations

import json
import py_compile
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

REQUIRED = [
    "services/database/models/automation.py",
    "services/database/migrations/versions/20260726_0010_v24_domain_automation.py",
    "services/worker/handlers.py",
    "services/worker/main.py",
    "services/api/app/services/job_queue.py",
    "services/api/app/services/operations.py",
    "services/api/app/routes/operations.py",
    "services/api/app/schemas/operations.py",
    "tests/unit/test_v24_domain_automation.py",
    "scripts/validation/Test-V2.4DomainAutomationRuntime.ps1",
    "docs/implementation/PHASE_13_V2.4_DOMAIN_AUTOMATION_IMPLEMENTATION_REPORT.md",
    "docs/api/V2.4_AUTOMATION_AND_OPERATIONS_API.md",
    "docs/operations/V2.4_BACKGROUND_DOMAIN_EXECUTION.md",
    "docs/security/V2.4_RETENTION_AND_DELIVERY_SAFETY.md",
    "docs/ux/V2.4_PLATFORM_OPERATIONS_EXPERIENCE.md",
    "docs/requirements/V2.4_ACCEPTANCE_CRITERIA.md",
    "docs/testing/V2.4_STATIC_VALIDATION_EVIDENCE.md",
    "docs/testing/V2.4_RELEASE_VALIDATION_REPORT.md",
    "docs/architecture/adr/ADR-018-durable-domain-automation.md",
    "docs/architecture/uml/v2.4/README.md",
]
missing = [item for item in REQUIRED if not (ROOT / item).exists()]
if missing:
    raise SystemExit("Missing v2.4 files: " + ", ".join(missing))

for rel in [
    "services/database/models/automation.py",
    "services/database/migrations/versions/20260726_0010_v24_domain_automation.py",
    "services/worker/handlers.py",
    "services/worker/main.py",
    "services/api/app/services/job_queue.py",
    "services/api/app/services/operations.py",
    "services/api/app/routes/operations.py",
    "services/api/app/schemas/operations.py",
    "scripts/validation/validate_v24_release.py",
]:
    py_compile.compile(str(ROOT / rel), doraise=True)

from services.api.app.main import app
from services.api.app.services.job_queue import ALLOWED_JOB_TYPES
from services.database.models import Base
from services.worker.handlers import HANDLERS

assert tuple(map(int, app.version.split("."))) >= (2, 4, 0)
assert len(Base.metadata.tables) >= 107
assert {
    "governance.notification_deliveries",
    "privacy.retention_runs",
    "privacy.retention_run_items",
} <= set(Base.metadata.tables)
assert ALLOWED_JOB_TYPES == set(HANDLERS)
for job_type in ALLOWED_JOB_TYPES:
    assert HANDLERS[job_type].__name__ != "owner_machine_handler_required"

paths = set(app.openapi()["paths"].keys())
for path in [
    "/api/v1/operations/schedules",
    "/api/v1/operations/schedules/{schedule_id}",
    "/api/v1/operations/notification-deliveries",
    "/api/v1/operations/retention-runs",
]:
    assert path in paths, path

catalogue = json.loads((ROOT / "services/database/seeds/role_permissions.json").read_text(encoding="utf-8"))
permission_codes = {item["code"] for item in catalogue["permissions"]}
required_permissions = {
    "operations.schedules.read", "operations.schedules.manage",
    "operations.deliveries.read", "operations.retention.read", "operations.retention.manage",
}
assert required_permissions <= permission_codes
roles = {item["code"]: set(item["permissions"]) for item in catalogue["roles"]}
assert required_permissions <= roles["institution_administrator"]
for role in ("head_of_department", "lecturer", "internal_moderator", "external_reviewer"):
    assert not required_permissions.intersection(roles[role])

migration = (ROOT / "services/database/migrations/versions/20260726_0010_v24_domain_automation.py").read_text(encoding="utf-8")
assert "enqueue_due_scheduled_jobs" in migration
assert "SECURITY DEFINER" in migration
assert "schedule_kind = 'interval'" in migration
handlers = (ROOT / "services/worker/handlers.py").read_text(encoding="utf-8")
for token in [
    "dispatch_notifications_handler", "publish_outbox_handler", "expire_external_access_handler",
    "apply_retention_handler", "generate_report_handler", "generate_audit_export_handler",
    "ingest_document_handler", "generate_export_handler",
]:
    assert token in handlers
assert "hard_delete_supported\": False" in handlers

web = (ROOT / "apps/web/src/components/commercial-governance-panels.tsx").read_text(encoding="utf-8")
assert "PlatformOperationsPanel" in web and "Run preview" in web
assert 'version = "2.6.0"' in (ROOT / "pyproject.toml").read_text(encoding="utf-8")
assert tuple(map(int, json.loads((ROOT / "apps/web/package.json").read_text(encoding="utf-8"))["version"].split("."))) >= (2, 4, 0)

uml_files = list((ROOT / "docs/architecture/uml/v2.4").glob("*.puml"))
assert len(uml_files) == 6
for file in uml_files:
    text = file.read_text(encoding="utf-8")
    assert text.lstrip().startswith("@startuml") and text.rstrip().endswith("@enduml"), file

print(
    "v2.4 release validation passed: durable domain handlers, governed interval schedules, "
    "notification delivery evidence, reversible retention runs, operations UI, role separation, "
    "documentation, diagrams, and version metadata are present."
)
