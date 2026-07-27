[CmdletBinding()]
param()
$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest
Set-Location (Resolve-Path (Join-Path $PSScriptRoot "..\.."))
docker compose stop postgres redis minio qdrant
Write-Host "Local data services stopped; named volumes were retained." -ForegroundColor Green
