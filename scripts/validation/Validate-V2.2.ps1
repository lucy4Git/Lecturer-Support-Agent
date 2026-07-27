[CmdletBinding()]
param([switch]$RunTests)
$ErrorActionPreference='Stop'
$Root=(Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
Push-Location $Root
try {
  python scripts/validation/validate_v22_release.py
  if ($LASTEXITCODE -ne 0) { throw 'v2.2 static release validation failed.' }
  if ($RunTests) {
    python -m pytest tests/unit -q
    if ($LASTEXITCODE -ne 0) { throw 'Unit tests failed.' }
  }
  Write-Host 'Lecturer Support Agent v2.2 analytics and governance release passed static validation.' -ForegroundColor Green
  Write-Host 'Runtime, RLS, provider, report and live-preview validation remain owner-machine pending.' -ForegroundColor Yellow
} finally { Pop-Location }
