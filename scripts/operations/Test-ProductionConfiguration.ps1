[CmdletBinding()]
param([string]$EnvironmentFile = '.env.production.local')
$ErrorActionPreference = 'Stop'
$Root = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
Set-Location $Root
if (-not (Test-Path $EnvironmentFile)) { throw "Missing $EnvironmentFile. Never commit this file." }
. "$Root\scripts\validation\Validation.Common.ps1"
Import-ProjectEnvironment -Path $EnvironmentFile -Override
$env:ENVIRONMENT = 'production'
$env:AI_ENABLE_DEVELOPMENT_MOCK = 'false'
python -c "from services.api.app.core.settings import Settings; Settings(_env_file=None); print('Production configuration validation passed.')"
if ($LASTEXITCODE -ne 0) { throw 'Production configuration validation failed.' }
docker compose --env-file $EnvironmentFile -f compose.production.yaml config --quiet
if ($LASTEXITCODE -ne 0) { throw 'Production Compose validation failed.' }
