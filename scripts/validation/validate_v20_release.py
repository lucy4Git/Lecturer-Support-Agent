from __future__ import annotations

import json
import py_compile
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
REQUIRED = [
    'VALIDATION_STATUS.md',
    'config/validation/owner-machine-profile.example.json',
    'data/schemas/owner_machine_validation_profile.schema.json',
    'scripts/validation/Invoke-ConsolidatedOwnerValidation.ps1',
    'scripts/validation/Test-OwnerMachinePrerequisites.ps1',
    'scripts/validation/Test-EnvironmentSafety.ps1',
    'scripts/validation/runtime_probe.py',
    'scripts/validation/scan_repository_secrets.py',
    'tests/unit/test_v20_validation_readiness.py',
    'tests/e2e/live-preview/public-and-role-workspaces.spec.ts',
    'apps/web/playwright.config.ts',
    'docs/implementation/PHASE_9_V2.0_VALIDATION_READINESS_IMPLEMENTATION_REPORT.md',
    'docs/operations/V2.0_CONSOLIDATED_OWNER_MACHINE_VALIDATION.md',
    'docs/testing/V2.0_RUNTIME_VALIDATION_MATRIX.md',
    'docs/testing/V2.0_FAILURE_TRIAGE_AND_ROLLBACK.md',
    'docs/requirements/V2.0_ACCEPTANCE_CRITERIA.md',
    'docs/architecture/adr/ADR-014-consolidated-owner-machine-validation-gate.md',
]
missing = [rel for rel in REQUIRED if not (ROOT / rel).exists()]
if missing:
    raise SystemExit('Missing v2.0 files: ' + ', '.join(missing))
for rel in ['scripts/validation/runtime_probe.py','scripts/validation/scan_repository_secrets.py','scripts/validation/validate_v20_release.py']:
    py_compile.compile(str(ROOT / rel), doraise=True)
profile = json.loads((ROOT/'config/validation/owner-machine-profile.example.json').read_text(encoding='utf-8'))
assert profile['required_services']['postgresql']['required'] is True
assert {'qwen3:8b','nomic-embed-text-v2-moe'} <= set(profile['required_ollama_models'])
assert {'static','live_preview','security','recovery'} <= set(profile['validation_stages'])
package = json.loads((ROOT/'apps/web/package.json').read_text(encoding='utf-8'))
assert tuple(map(int, package['version'].split('.'))) >= (2, 0, 0)
assert '@playwright/test' in package['devDependencies']
pyproject = (ROOT/'pyproject.toml').read_text(encoding='utf-8')
assert 'version = "2.' in pyproject
main = (ROOT/'services/api/app/main.py').read_text(encoding='utf-8')
assert 'version="2.' in main
orchestrator = (ROOT/'scripts/validation/Invoke-ConsolidatedOwnerValidation.ps1').read_text(encoding='utf-8')
for token in ['StartInfrastructure', 'RunLivePreview', 'runtime_probe.py', "@('playwright','test')", 'validation-summary.json']:
    assert token in orchestrator
assert 'Start-DatabaseStack.ps1' in orchestrator
assert not re.search(r'(?i)start-process\s+.*docker desktop', orchestrator)
print('v2.0 release validation passed: consolidated owner-machine harness, evidence capture, live-preview tests, safety gate, documentation, and version metadata are present.')
