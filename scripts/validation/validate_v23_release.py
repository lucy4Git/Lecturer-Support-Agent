from __future__ import annotations

import json
import py_compile
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

REQUIRED = [
    "services/database/models/reliability.py",
    "services/database/migrations/versions/20260726_0009_v23_operational_hardening.py",
    "services/api/app/core/hardening.py",
    "services/api/app/observability/logging.py",
    "services/api/app/observability/metrics.py",
    "services/api/app/integrations/malware_scanner.py",
    "services/api/app/services/job_queue.py",
    "services/api/app/services/operations.py",
    "services/api/app/services/readiness.py",
    "services/api/app/routes/operations.py",
    "services/worker/main.py",
    "services/worker/handlers.py",
    "tests/unit/test_v23_operational_hardening.py",
    "compose.production.yaml",
    "infrastructure/docker/api.Dockerfile",
    "infrastructure/docker/worker.Dockerfile",
    "infrastructure/docker/web.Dockerfile",
    "infrastructure/gateway/Caddyfile",
    "infrastructure/observability/prometheus.yml",
    "infrastructure/observability/alerts/lsa.rules.yml",
    "infrastructure/kubernetes/base/kustomization.yaml",
    "scripts/operations/Backup-Platform.ps1",
    "scripts/operations/Restore-Platform.ps1",
    "scripts/operations/Test-BackupManifest.ps1",
    "scripts/operations/Start-BackgroundWorker.ps1",
    "scripts/database/ensure_database_roles.py",
    "scripts/validation/Test-V2.3OperationalRuntime.ps1",
    "scripts/data/generate_synthetic_academic_corpus.py",
    "scripts/data/validate_institution_onboarding.py",
    "scripts/database/ensure_database_roles.py",
    "data/schemas/institution_onboarding_package.schema.json",
    "data/manifests/example_institution_onboarding_package.json",
    "data/fixtures/safe/synthetic_academic_corpus_v2.3.jsonl",
    "docs/implementation/PHASE_12_V2.3_PRODUCTION_HARDENING_IMPLEMENTATION_REPORT.md",
    "docs/api/V2.3_OPERATIONS_AND_RELIABILITY_API.md",
    "docs/security/V2.3_PRODUCTION_HARDENING.md",
    "docs/operations/V2.3_BACKGROUND_JOBS_AND_WORKERS.md",
    "docs/operations/V2.3_BACKUP_RESTORE_AND_DR.md",
    "docs/operations/V2.3_DEPLOYMENT_AND_OBSERVABILITY.md",
    "docs/operations/V2.3_OWNER_MACHINE_VALIDATION.md",
    "docs/data/V2.3_SYNTHETIC_CORPUS_AND_ONBOARDING_PACK.md",
    "docs/requirements/V2.3_ACCEPTANCE_CRITERIA.md",
    "docs/testing/V2.3_STATIC_VALIDATION_EVIDENCE.md",
    "docs/testing/V2.3_RELEASE_VALIDATION_REPORT.md",
    "docs/architecture/adr/ADR-017-durable-jobs-and-production-hardening.md",
    "docs/architecture/uml/v2.3/README.md",
]
missing = [item for item in REQUIRED if not (ROOT / item).exists()]
if missing:
    raise SystemExit("Missing v2.3 files: " + ", ".join(missing))

for rel in [
    "services/database/models/reliability.py",
    "services/api/app/core/hardening.py",
    "services/api/app/observability/logging.py",
    "services/api/app/observability/metrics.py",
    "services/api/app/integrations/malware_scanner.py",
    "services/api/app/services/job_queue.py",
    "services/api/app/services/operations.py",
    "services/api/app/services/readiness.py",
    "services/api/app/routes/operations.py",
    "services/worker/main.py",
    "scripts/data/generate_synthetic_academic_corpus.py",
    "scripts/data/validate_institution_onboarding.py",
    "scripts/database/ensure_database_roles.py",
    "scripts/validation/validate_v23_release.py",
]:
    py_compile.compile(str(ROOT / rel), doraise=True)

from services.api.app.main import app
from services.database.models import Base

assert tuple(map(int, app.version.split("."))) >= (2, 3, 0)
assert len(Base.metadata.tables) >= 104
required_tables = {
    "operations.background_jobs",
    "operations.background_job_attempts",
    "operations.dead_letter_jobs",
    "operations.scheduled_jobs",
    "operations.backup_runs",
    "operations.restore_drills",
}
assert required_tables <= set(Base.metadata.tables)

paths = set(app.openapi()["paths"].keys())
for path in [
    "/health",
    "/ready",
    "/metrics",
    "/api/v1/operations/jobs",
    "/api/v1/operations/summary",
    "/api/v1/operations/dead-letters/{dead_letter_id}/replay",
    "/api/v1/operations/backups",
    "/api/v1/operations/backups/{backup_run_id}/restore-drills",
]:
    assert path in paths, path

catalogue = json.loads((ROOT / "services/database/seeds/role_permissions.json").read_text(encoding="utf-8"))
permission_codes = {item["code"] for item in catalogue["permissions"]}
required_permissions = {
    "operations.jobs.read",
    "operations.jobs.manage",
    "operations.backups.read",
    "operations.backups.manage",
}
assert required_permissions <= permission_codes
roles = {item["code"]: set(item["permissions"]) for item in catalogue["roles"]}
assert required_permissions <= roles["institution_administrator"]
for role in ("head_of_department", "lecturer", "internal_moderator", "external_reviewer"):
    assert not required_permissions.intersection(roles[role])

migration = (ROOT / "services/database/migrations/versions/20260726_0009_v23_operational_hardening.py").read_text(encoding="utf-8")
rls = (ROOT / "services/database/policies/row_level_security.sql").read_text(encoding="utf-8")
assert 'CREATE SCHEMA IF NOT EXISTS "operations"' in migration
assert "row_level_security.sql" in migration
assert "claim_next_job" in migration and "recover_expired_job_leases" in migration
assert "lsa_worker" in migration and "lsa_worker" in rls
assert "'operations'" in rls
role_init = (ROOT / "infrastructure/database/postgresql/init/01-create-application-role.sh").read_text(encoding="utf-8")
role_bootstrap = (ROOT / "scripts/database/ensure_database_roles.py").read_text(encoding="utf-8")
assert "lsa_worker" in role_init and "NOBYPASSRLS" in role_init
assert "lsa_worker" in role_bootstrap and "NOBYPASSRLS" in role_bootstrap

settings = (ROOT / "services/api/app/core/settings.py").read_text(encoding="utf-8")
for token in [
    "rate_limit_fail_closed",
    "malware_scan_fail_closed",
    "metrics_token",
    "content_security_policy",
    "background_job_lease_seconds",
]:
    assert token in settings

bulk = (ROOT / "services/api/app/routes/bulk_uploads.py").read_text(encoding="utf-8")
assert "get_malware_scanner" in bulk
assert "scan_bytes" in bulk
hardening = (ROOT / "services/api/app/core/hardening.py").read_text(encoding="utf-8")
assert "limited_receive" in hardening and "_RequestBodyTooLarge" in hardening
for manifest in ("api.yaml", "worker.yaml", "web.yaml"):
    k8s = (ROOT / "infrastructure/kubernetes/base" / manifest).read_text(encoding="utf-8")
    assert "readOnlyRootFilesystem: true" in k8s and "mountPath: /tmp" in k8s

compose = (ROOT / "compose.production.yaml").read_text(encoding="utf-8")
for token in ["MALWARE_SCAN_FAIL_CLOSED", "RATE_LIMIT_FAIL_CLOSED", "METRICS_TOKEN", "worker:", "clamav:"]:
    assert token in compose
assert "change-me" not in compose.lower()

schema = json.loads((ROOT / "data/schemas/institution_onboarding_package.schema.json").read_text(encoding="utf-8"))
assert schema["$schema"].endswith("2020-12/schema")
package = json.loads((ROOT / "data/manifests/example_institution_onboarding_package.json").read_text(encoding="utf-8"))
assert package["governance"]["contains_personal_data"] is False

records = [json.loads(line) for line in (ROOT / "data/fixtures/safe/synthetic_academic_corpus_v2.3.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
assert len(records) == 36
assert len({item["discipline"] for item in records}) == 12
assert all(item["synthetic"] is True and len(item["sha256"]) == 64 for item in records)

web_package = json.loads((ROOT / "apps/web/package.json").read_text(encoding="utf-8"))
assert tuple(map(int, web_package["version"].split("."))) >= (2, 3, 0)
assert 'version = "2.' in (ROOT / "pyproject.toml").read_text(encoding="utf-8")

uml_files = list((ROOT / "docs/architecture/uml/v2.3").glob("*.puml"))
assert len(uml_files) == 8
for file in uml_files:
    text = file.read_text(encoding="utf-8")
    assert text.lstrip().startswith("@startuml") and text.rstrip().endswith("@enduml"), file

print(
    "v2.3 release validation passed: durable jobs, production hardening, malware scanning, "
    "observability, backup/restore automation, deployment assets, synthetic corpus, onboarding "
    "validation, role separation, documentation, diagrams, and version metadata are present."
)
