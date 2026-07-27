[CmdletBinding()]
param([switch]$PullImages)
$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest
Set-Location (Resolve-Path (Join-Path $PSScriptRoot "..\.."))

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    throw "Docker CLI is not installed. Install Docker Desktop or another Docker engine first."
}
docker info *> $null
if ($LASTEXITCODE -ne 0) { throw "Docker is not running. Start it manually; this script will not launch Docker Desktop." }
if ($PullImages) { docker compose pull postgres redis minio minio-bootstrap; if ($LASTEXITCODE -ne 0) { throw 'Docker image pull failed.' } }
docker compose up -d postgres redis minio qdrant
if ($LASTEXITCODE -ne 0) { throw 'Docker Compose service startup failed.' }
docker compose run --rm minio-bootstrap
if ($LASTEXITCODE -ne 0) { throw 'MinIO bootstrap failed.' }
Write-Host "Local data services started. Run Initialize-Database.ps1 next." -ForegroundColor Green
