[CmdletBinding()]
param([switch]$ConfirmReset)
$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest
if (-not $ConfirmReset) {
    throw "Destructive reset blocked. Re-run with -ConfirmReset after confirming no required data is present."
}
Set-Location (Resolve-Path (Join-Path $PSScriptRoot "..\.."))
docker compose down -v
Write-Host "Development containers and named volumes were removed. Docker Desktop was not started or stopped." -ForegroundColor Yellow
