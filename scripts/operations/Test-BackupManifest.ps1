[CmdletBinding()]
param([Parameter(Mandatory=$true)][string]$BackupDirectory)
$ErrorActionPreference = 'Stop'
$backup = (Resolve-Path $BackupDirectory).Path
$manifestPath = Join-Path $backup 'backup-manifest.json'
$manifest = Get-Content $manifestPath -Raw | ConvertFrom-Json
foreach ($component in $manifest.components) {
    $path = Join-Path $backup $component.name
    if (-not (Test-Path $path)) { throw "Missing: $($component.name)" }
    $actual = (Get-FileHash $path -Algorithm SHA256).Hash.ToLower()
    if ($actual -ne ([string]$component.sha256).ToLower()) { throw "Checksum failed: $($component.name)" }
}
Write-Host "Backup manifest verified: $backup" -ForegroundColor Green
