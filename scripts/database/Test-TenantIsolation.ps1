[CmdletBinding()]
param()
$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest
Set-Location (Resolve-Path (Join-Path $PSScriptRoot "..\.."))
Get-Content .env | ForEach-Object {
    if ($_ -match '^\s*([^#][^=]+)=(.*)$') {
        [Environment]::SetEnvironmentVariable($matches[1].Trim(), $matches[2].Trim(), "Process")
    }
}
python -m pytest tests/integration/test_tenant_isolation.py -m "integration and security" -v
if ($LASTEXITCODE -ne 0) { throw 'Tenant-isolation validation failed.' }
