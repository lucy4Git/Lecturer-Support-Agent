[CmdletBinding()]
param([switch]$IncludeOwnerMachineChecks)

$ErrorActionPreference = "Stop"
$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
Push-Location $ProjectRoot
try {
    python .\scripts\validation\validate_v18_release.py
    if ($LASTEXITCODE -ne 0) { throw "v1.8 static validation failed." }
    if ($IncludeOwnerMachineChecks) {
        .\scripts\database\Run-Migrations.ps1
        python -m pytest tests\integration -v
        .\scripts\database\Test-TenantIsolation.ps1
    }
    Write-Host "Lecturer Support Agent v1.8 validation completed." -ForegroundColor Green
}
finally { Pop-Location }
