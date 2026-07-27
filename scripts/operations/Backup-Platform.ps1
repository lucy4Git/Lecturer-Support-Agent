[CmdletBinding()]
param(
    [string]$OutputDirectory = 'runtime\backups',
    [string]$ComposeFile = 'compose.yaml',
    [switch]$IncludeQdrant,
    [switch]$IncludeMinio
)
$ErrorActionPreference = 'Stop'
$Root = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
Set-Location $Root
if (-not (Test-Path '.env')) { throw '.env is required and must remain local/ignored.' }
. "$Root\scripts\validation\Validation.Common.ps1"
Import-ProjectEnvironment -Path '.env' -Override
$stamp = (Get-Date).ToUniversalTime().ToString('yyyyMMddTHHmmssZ')
$destination = Join-Path $Root (Join-Path $OutputDirectory $stamp)
New-Item -ItemType Directory -Path $destination -Force | Out-Null

$postgresContainer = (& docker compose -f $ComposeFile ps -q postgres).Trim()
if (-not $postgresContainer) { throw 'PostgreSQL container is not running.' }
$dbFile = Join-Path $destination 'postgres.dump'
& docker compose -f $ComposeFile exec -T postgres sh -lc "pg_dump -U `$POSTGRES_USER -d `$POSTGRES_DB -Fc -f /tmp/lsa-postgres.dump"
if ($LASTEXITCODE -ne 0) { throw 'PostgreSQL backup failed.' }
& docker cp "${postgresContainer}:/tmp/lsa-postgres.dump" $dbFile
& docker compose -f $ComposeFile exec -T postgres rm -f /tmp/lsa-postgres.dump | Out-Null

if ($IncludeMinio) {
    $container = (& docker compose -f $ComposeFile ps -q minio).Trim()
    if (-not $container) { throw 'MinIO container is not running.' }
    & docker compose -f $ComposeFile exec -T minio sh -lc 'tar -C /data -czf /tmp/lsa-minio.tgz .'
    if ($LASTEXITCODE -ne 0) { throw 'MinIO backup failed.' }
    & docker cp "${container}:/tmp/lsa-minio.tgz" (Join-Path $destination 'minio.tgz')
    & docker compose -f $ComposeFile exec -T minio rm -f /tmp/lsa-minio.tgz | Out-Null
}

if ($IncludeQdrant) {
    $container = (& docker compose -f $ComposeFile ps -q qdrant).Trim()
    if (-not $container) { throw 'Qdrant container is not running.' }
    & docker compose -f $ComposeFile exec -T qdrant sh -lc 'tar -C /qdrant/storage -czf /tmp/lsa-qdrant.tgz .'
    if ($LASTEXITCODE -ne 0) { throw 'Qdrant backup failed.' }
    & docker cp "${container}:/tmp/lsa-qdrant.tgz" (Join-Path $destination 'qdrant.tgz')
    & docker compose -f $ComposeFile exec -T qdrant rm -f /tmp/lsa-qdrant.tgz | Out-Null
}

Copy-Item '.env.example' (Join-Path $destination 'env.example')
Copy-Item 'compose.yaml' (Join-Path $destination 'compose.yaml')
$files = Get-ChildItem $destination -File | Sort-Object Name
$manifest = [ordered]@{
    format_version = '1.0'
    created_at = (Get-Date).ToUniversalTime().ToString('o')
    project_version = '2.3.0'
    components = @($files | ForEach-Object {
        [ordered]@{ name=$_.Name; size_bytes=$_.Length; sha256=(Get-FileHash $_.FullName -Algorithm SHA256).Hash.ToLower() }
    })
}
$manifestPath = Join-Path $destination 'backup-manifest.json'
$manifest | ConvertTo-Json -Depth 6 | Set-Content $manifestPath -Encoding utf8
(Get-FileHash $manifestPath -Algorithm SHA256).Hash.ToLower() | Set-Content (Join-Path $destination 'backup-manifest.sha256')
Write-Host "Backup created: $destination" -ForegroundColor Green
