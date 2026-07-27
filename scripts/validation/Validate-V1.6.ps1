[CmdletBinding()]
param([switch]$RunOwnerMachineChecks)

$ErrorActionPreference = "Stop"
$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
Push-Location $ProjectRoot
try {
    python .\scripts\validation\validate_data_foundation.py
    python .\scripts\validation\validate_multi_provider_pack.py
    python .\scripts\validation\validate_v13_foundation.py
    python .\scripts\validation\validate_v14_release.py
    python .\scripts\validation\validate_v15_release.py
    python .\scripts\validation\validate_v16_release.py
    python -m pytest tests\unit -v
    node .\scripts\validation\Validate-TypeScriptSyntax.js
    if ($RunOwnerMachineChecks) {
        .\scripts\database\Run-Migrations.ps1
        .\scripts\database\Test-TenantIsolation.ps1
        Write-Host "Run a real upload, ingestion, Qdrant retrieval, conversation attachment, and browser preview before release acceptance."
    }
} finally { Pop-Location }
