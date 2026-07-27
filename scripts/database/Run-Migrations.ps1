[CmdletBinding()]
param()
$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest
Set-Location (Resolve-Path (Join-Path $PSScriptRoot "..\.."))
if (-not (Test-Path ".env")) { throw ".env is missing. Copy .env.example to .env first." }

Get-Content .env | ForEach-Object {
    if ($_ -match '^\s*([^#][^=]+)=(.*)$') {
        [Environment]::SetEnvironmentVariable($matches[1].Trim(), $matches[2].Trim(), "Process")
    }
}
python scripts/database/ensure_database_roles.py
if ($LASTEXITCODE -ne 0) { throw 'Database role provisioning failed.' }
python -m alembic upgrade head
if ($LASTEXITCODE -ne 0) { throw 'Alembic upgrade failed.' }
python -m alembic current
if ($LASTEXITCODE -ne 0) { throw 'Alembic current failed.' }
