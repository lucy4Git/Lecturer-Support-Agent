[CmdletBinding()]
param([switch]$RunTests)
$ErrorActionPreference='Stop'
$Root=(Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
Set-Location $Root
python scripts/validation/validate_v25_completion.py
node scripts/validation/Validate-TypeScriptSyntax.js
if ($RunTests) { python -m pytest tests/unit -q }
Write-Host 'v2.5 static validation passed.' -ForegroundColor Green
