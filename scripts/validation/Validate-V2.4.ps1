[CmdletBinding()]
param([switch]$RunTests)
$ErrorActionPreference='Stop'
$Root=(Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
Push-Location $Root
try {
  python scripts/validation/validate_v24_release.py
  if ($LASTEXITCODE -ne 0) { throw 'v2.4 static release validation failed.' }
  if ($RunTests) {
    python -m pytest tests/unit -q
    if ($LASTEXITCODE -ne 0) { throw 'Unit tests failed.' }
  }
  Write-Host 'Lecturer Support Agent v2.4 durable domain automation passed static validation.' -ForegroundColor Green
  Write-Host 'Live schedules, worker execution, MinIO, Qdrant, Ollama, backup and browser validation remain owner-machine pending.' -ForegroundColor Yellow
} finally { Pop-Location }
