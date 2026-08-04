from __future__ import annotations

import json
import py_compile
import sys
from pathlib import Path

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

REQUIRED = [
    "services/database/models/completion.py",
    "services/database/migrations/versions/20260726_0011_v25_gap_closure.py",
    "services/api/app/core/mfa.py",
    "services/api/app/integrations/email_delivery.py",
    "services/api/app/integrations/oidc.py",
    "services/api/app/integrations/academic_systems.py",
    "services/api/app/services/account_security.py",
    "services/api/app/services/sso_authentication.py",
    "services/api/app/services/enterprise_integrations.py",
    "services/api/app/services/privacy_completion.py",
    "services/api/app/services/evaluation_capture.py",
    "services/api/app/services/data_preparation.py",
    "services/api/app/routes/completion.py",
    "services/worker/backup_execution.py",
    "data/schemas/dataset_source_catalogue.schema.json",
    "data/catalogues/verified_oer_and_metadata_sources_v2.5.json",
    "data/evaluation/pilot_evaluation_instrument_v2.5.json",
    "packages/contracts/src/enterprise_integration_contracts.schema.json",
    "packages/contracts/src/claim_citation_verification.schema.json",
    "apps/web/public/manifest.webmanifest",
    "apps/web/public/sw.js",
    "docs/implementation/PHASE_14_V2.5_COMPLETION_GAP_CLOSURE_IMPLEMENTATION_REPORT.md",
    "docs/api/V2.5_COMPLETION_ENTERPRISE_COMMERCIAL_API.md",
    "docs/requirements/V2.5_ACCEPTANCE_CRITERIA.md",
    "docs/operations/V2.5_OWNER_MACHINE_VALIDATION.md",
    "docs/testing/V2.5_STATIC_VALIDATION_EVIDENCE.md",
    "docs/testing/V2.5_RELEASE_VALIDATION_REPORT.md",
    "docs/architecture/adr/ADR-019-completion-gap-closure-and-enterprise-boundaries.md",
    "docs/architecture/uml/v2.5/README.md",
]
missing = [item for item in REQUIRED if not (ROOT / item).is_file()]
if missing:
    raise SystemExit("Missing v2.5 files: " + ", ".join(missing))

for rel in [
    "services/database/models/completion.py",
    "services/database/migrations/versions/20260726_0011_v25_gap_closure.py",
    "services/api/app/core/mfa.py",
    "services/api/app/integrations/email_delivery.py",
    "services/api/app/integrations/oidc.py",
    "services/api/app/integrations/academic_systems.py",
    "services/api/app/services/account_security.py",
    "services/api/app/services/sso_authentication.py",
    "services/api/app/services/enterprise_integrations.py",
    "services/api/app/services/privacy_completion.py",
    "services/api/app/services/evaluation_capture.py",
    "services/api/app/services/data_preparation.py",
    "services/api/app/routes/completion.py",
    "services/worker/backup_execution.py",
    "services/worker/handlers.py",
]:
    py_compile.compile(str(ROOT / rel), doraise=True)

from services.api.app.main import app
from services.api.app.services.job_queue import ALLOWED_JOB_TYPES
from services.database.models import Base
from services.worker.handlers import HANDLERS

assert app.version == "2.6.0"
assert len(Base.metadata.tables) == 125
expected_tables = {
    "iam.account_challenges", "iam.mfa_devices", "iam.mfa_recovery_codes",
    "iam.sso_connections", "iam.federated_identities", "governance.outbound_messages",
    "governance.integration_connections", "operations.integration_sync_runs",
    "governance.external_record_mappings", "privacy.legal_holds",
    "privacy.deletion_requests", "privacy.deletion_actions", "analytics.user_feedback",
    "analytics.evaluation_campaigns", "analytics.evaluation_responses",
    "governance.dataset_source_records", "operations.dataset_acquisition_runs",
}
assert expected_tables <= set(Base.metadata.tables)
assert ALLOWED_JOB_TYPES == set(HANDLERS)
assert HANDLERS["operations.backup"].__name__ == "backup_handler"
assert HANDLERS["operations.restore_drill"].__name__ == "restore_drill_handler"
assert all(handler.__name__ != "owner_machine_handler_required" for handler in HANDLERS.values())

paths = set(app.openapi()["paths"].keys())
for path in [
    "/api/v1/auth/password-reset/request", "/api/v1/auth/password-reset/confirm",
    "/api/v1/auth/sso/start", "/api/v1/auth/sso/callback", "/api/v1/auth/sso/exchange",
    "/api/v1/account/mfa/enrol", "/api/v1/integrations", "/api/v1/sso-connections",
    "/api/v1/privacy/legal-holds", "/api/v1/privacy/deletion-requests",
    "/api/v1/feedback", "/api/v1/evaluation/campaigns", "/api/v1/data-sources",
]:
    assert path in paths, path

catalogue = json.loads((ROOT / "services/database/seeds/role_permissions.json").read_text(encoding="utf-8"))
permissions = {item["code"] for item in catalogue["permissions"]}
required = {
    "integrations.read", "integrations.manage", "sso.manage",
    "privacy.legal_holds.manage", "privacy.deletion.manage", "privacy.deletion.approve",
    "feedback.submit", "evaluation.manage", "evaluation.participate",
    "datasets.manage", "datasets.approve", "datasets.acquire",
}
assert required <= permissions
roles = {item["code"]: set(item["permissions"]) for item in catalogue["roles"]}
assert {"integrations.manage", "sso.manage", "privacy.deletion.approve"} <= roles["institution_administrator"]
assert "academic.assign_lecturer" not in roles["institution_administrator"]
assert "academic.assign_lecturer" in roles["head_of_department"]
assert "integrations.manage" not in roles["head_of_department"]

schema = json.loads((ROOT / "data/schemas/dataset_source_catalogue.schema.json").read_text(encoding="utf-8"))
source_catalogue = json.loads((ROOT / "data/catalogues/verified_oer_and_metadata_sources_v2.5.json").read_text(encoding="utf-8"))
Draft202012Validator.check_schema(schema)
Draft202012Validator(schema).validate(source_catalogue)
assert not any("full_text" in source for source in source_catalogue["sources"])
assert any(source["source_key"] == "openalex_metadata" for source in source_catalogue["sources"])

assert 'version = "2.6.0"' in (ROOT / "pyproject.toml").read_text(encoding="utf-8")
assert json.loads((ROOT / "apps/web/package.json").read_text(encoding="utf-8"))["version"] == "2.6.0"
assert "BACKUP_STORAGE_ENCRYPTION_ATTESTED" in (ROOT / ".env.example").read_text(encoding="utf-8")
# .env must be git-ignored (may exist on owner machine, must never be tracked)
import subprocess as _sp
_git_check = _sp.run(
    ["git", "ls-files", "--error-unmatch", ".env"],
    cwd=ROOT, capture_output=True
)
assert _git_check.returncode != 0, ".env is tracked by git — must be git-ignored"

uml_files = list((ROOT / "docs/architecture/uml/v2.5").glob("*.puml"))
assert len(uml_files) == 7
for file in uml_files:
    text = file.read_text(encoding="utf-8")
    assert text.lstrip().startswith("@startuml") and text.rstrip().endswith("@enduml"), file

print(
    "v2.5 completion validation passed: account recovery, MFA, OIDC, enterprise adapters, "
    "legal holds/deletion, connected backup and restore-drill handlers, real-data rights gates, "
    "feedback/evaluation, PWA assets, commercial templates, role separation, and version metadata are present."
)
