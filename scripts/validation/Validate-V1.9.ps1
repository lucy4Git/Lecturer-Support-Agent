[CmdletBinding()]
param([switch]$RunTests)
$ErrorActionPreference='Stop'
$Root=(Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
Push-Location $Root
try {
  python scripts/validation/validate_v19_release.py
  if ($RunTests) { python -m pytest tests/unit -q }
  Write-Host 'Lecturer Support Agent v1.9 validation passed.' -ForegroundColor Green
} finally { Pop-Location }
