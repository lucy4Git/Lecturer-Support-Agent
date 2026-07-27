[CmdletBinding()]
param([switch]$RunTests)
$ErrorActionPreference='Stop'
$Root=(Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
Push-Location $Root
try {
  python scripts/validation/validate_v23_release.py
  if ($LASTEXITCODE -ne 0) { throw 'v2.3 static release validation failed.' }
  python scripts/data/validate_institution_onboarding.py data/manifests/example_institution_onboarding_package.json
  if ($LASTEXITCODE -ne 0) { throw 'Institution onboarding validation failed.' }
  if ($RunTests) {
    python -m pytest tests/unit -q
    if ($LASTEXITCODE -ne 0) { throw 'Unit tests failed.' }
  }
  Write-Host 'Lecturer Support Agent v2.3 operational hardening release passed static validation.' -ForegroundColor Green
  Write-Host 'Live jobs, malware scanning, backups, deployment, readiness and browser validation remain owner-machine pending.' -ForegroundColor Yellow
} finally { Pop-Location }
