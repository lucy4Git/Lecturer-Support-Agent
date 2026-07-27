[CmdletBinding(SupportsShouldProcess=$true, ConfirmImpact='High')]
param(
    [Parameter(Mandatory=$true)][string]$BackupDirectory,
    [string]$ComposeFile = 'compose.yaml',
    [switch]$RestoreMinio,
    [switch]$RestoreQdrant,
    [switch]$ConfirmDestructive
)
$ErrorActionPreference = 'Stop'
if (-not $ConfirmDestructive) { throw 'Pass -ConfirmDestructive after reviewing the restore plan.' }
$Root = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
Set-Location $Root
$backup = (Resolve-Path $BackupDirectory).Path
$manifest = Get-Content (Join-Path $backup 'backup-manifest.json') -Raw | ConvertFrom-Json
foreach ($component in $manifest.components) {
    $path = Join-Path $backup $component.name
    if (-not (Test-Path $path)) { throw "Missing backup component: $($component.name)" }
    $actual = (Get-FileHash $path -Algorithm SHA256).Hash.ToLower()
    if ($actual -ne ([string]$component.sha256).ToLower()) { throw "Checksum mismatch: $($component.name)" }
}
if (-not $PSCmdlet.ShouldProcess('Lecturer Support Agent data services', 'Restore backup')) { return }

$postgresContainer = (& docker compose -f $ComposeFile ps -q postgres).Trim()
if (-not $postgresContainer) { throw 'PostgreSQL container is not running.' }
& docker cp (Join-Path $backup 'postgres.dump') "${postgresContainer}:/tmp/lsa-postgres.dump"
& docker compose -f $ComposeFile exec -T postgres sh -lc "pg_restore -U `$POSTGRES_USER -d `$POSTGRES_DB --clean --if-exists --no-owner /tmp/lsa-postgres.dump"
if ($LASTEXITCODE -ne 0) { throw 'PostgreSQL restore failed.' }
& docker compose -f $ComposeFile exec -T postgres rm -f /tmp/lsa-postgres.dump | Out-Null

if ($RestoreMinio -and (Test-Path (Join-Path $backup 'minio.tgz'))) {
    $container = (& docker compose -f $ComposeFile ps -q minio).Trim()
    & docker cp (Join-Path $backup 'minio.tgz') "${container}:/tmp/lsa-minio.tgz"
    & docker compose -f $ComposeFile exec -T minio sh -lc 'rm -rf /data/* && tar -C /data -xzf /tmp/lsa-minio.tgz'
    if ($LASTEXITCODE -ne 0) { throw 'MinIO restore failed.' }
}
if ($RestoreQdrant -and (Test-Path (Join-Path $backup 'qdrant.tgz'))) {
    $container = (& docker compose -f $ComposeFile ps -q qdrant).Trim()
    & docker cp (Join-Path $backup 'qdrant.tgz') "${container}:/tmp/lsa-qdrant.tgz"
    & docker compose -f $ComposeFile exec -T qdrant sh -lc 'rm -rf /qdrant/storage/* && tar -C /qdrant/storage -xzf /tmp/lsa-qdrant.tgz'
    if ($LASTEXITCODE -ne 0) { throw 'Qdrant restore failed.' }
}
Write-Host 'Restore completed. Run migrations, readiness probes, tenant-isolation tests, and functional smoke tests before reopening access.' -ForegroundColor Yellow
