[CmdletBinding()]
param(
    [switch]$InstallDependencies,
    [switch]$SeedDemonstrationData,
    [switch]$StartServices
)
$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest
$root = Resolve-Path (Join-Path $PSScriptRoot "..\..")
Set-Location $root

if (-not (Test-Path ".env")) {
    Copy-Item ".env.example" ".env"
    Write-Warning "Created .env from the safe template. Replace every change-* development password before shared deployment."
}
if ($StartServices) { & "$PSScriptRoot\Start-DatabaseStack.ps1" }
if ($InstallDependencies) { python -m pip install -e ".[dev]" }
& "$PSScriptRoot\Run-Migrations.ps1"
& "$PSScriptRoot\Initialize-Qdrant.ps1"
if ($SeedDemonstrationData) { & "$PSScriptRoot\Seed-DemonstrationData.ps1" }
Write-Host "Database foundation initialized." -ForegroundColor Green
