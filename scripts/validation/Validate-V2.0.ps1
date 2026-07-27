[CmdletBinding()]
param([switch]$RunTests)
$ErrorActionPreference='Stop'
$Root=(Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
Push-Location $Root
try {
  python scripts/validation/validate_v20_release.py
  if ($LASTEXITCODE -ne 0) { throw 'v2.0 static release validation failed.' }
  if ($RunTests) { python -m pytest tests/unit -q; if ($LASTEXITCODE -ne 0) { throw 'Unit tests failed.' } }
  Write-Host 'Lecturer Support Agent v2.0 validation-readiness pack passed static validation.' -ForegroundColor Green
} finally { Pop-Location }
