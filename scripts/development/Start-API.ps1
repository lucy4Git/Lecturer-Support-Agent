[CmdletBinding()]
param([switch]$InstallDependencies)
$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest
Set-Location (Resolve-Path (Join-Path $PSScriptRoot "..\.."))
if (-not (Test-Path ".env")) { throw ".env is missing. Copy .env.example and initialise local secrets." }
Get-Content .env | ForEach-Object {
    if ($_ -match '^\s*([^#][^=]+)=(.*)$') {
        [Environment]::SetEnvironmentVariable($matches[1].Trim(), $matches[2].Trim(), "Process")
    }
}
if ($InstallDependencies) { python -m pip install -e ".[dev]" }
python -m uvicorn services.api.app.main:app --reload --host 127.0.0.1 --port 8000
