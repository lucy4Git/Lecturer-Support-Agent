[CmdletBinding(SupportsShouldProcess)]
param(
    [Parameter(Mandatory=$true)][string]$DumpFile,
    [Parameter(Mandatory=$true)][string]$ExpectedSha256,
    [switch]$Approved
)
$ErrorActionPreference = "Stop"
if (-not $Approved) { throw "Import requires -Approved after data-owner and legal review." }
if (-not $env:MIGRATION_DATABASE_URL) { throw "Destination MIGRATION_DATABASE_URL is required." }
$actual = (Get-FileHash $DumpFile -Algorithm SHA256).Hash.ToLower()
if ($actual -ne $ExpectedSha256.ToLower()) { throw "Approved dump checksum mismatch." }
$url = $env:MIGRATION_DATABASE_URL -replace '^postgresql\+psycopg://', 'postgresql://'
if ($PSCmdlet.ShouldProcess($url, "Restore approved application data")) {
  & pg_restore --dbname=$url --data-only --no-owner --no-privileges --single-transaction --exit-on-error $DumpFile
  if ($LASTEXITCODE -ne 0) { throw "pg_restore failed with exit code $LASTEXITCODE" }
}
Write-Host "Approved relational data imported. Run seed_foundation only in staging to regenerate secure test credentials."
