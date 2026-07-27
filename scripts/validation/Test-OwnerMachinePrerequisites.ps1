[CmdletBinding()]
param(
    [string]$ProfilePath = 'config/validation/owner-machine-profile.example.json',
    [switch]$RequireBrowserTooling
)
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
$Root = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
Set-Location $Root
if (-not (Test-Path $ProfilePath)) { throw "Validation profile not found: $ProfilePath" }
$profile = Get-Content $ProfilePath -Raw | ConvertFrom-Json
$required = @('python','node','npm','docker','ollama','git')
if ($RequireBrowserTooling) { $required += 'npx' }
$rows = foreach ($name in $required) {
    $command = Get-Command $name -ErrorAction SilentlyContinue
    [pscustomobject]@{ tool=$name; available=[bool]$command; path=if($command){$command.Source}else{''} }
}
$rows | Format-Table -AutoSize
$missing = @($rows | Where-Object { -not $_.available })
if ($missing.Count) { throw "Missing prerequisite tool(s): $($missing.tool -join ', ')" }
docker info *> $null
if ($LASTEXITCODE -ne 0) { throw 'Docker CLI exists but the Docker engine is not running. Start Docker Desktop manually.' }
$ollamaBase = [string]$profile.required_services.ollama.endpoint
$tags = Invoke-RestMethod -Uri ($ollamaBase.TrimEnd('/') + '/api/tags') -Method Get -TimeoutSec 10
$installed = @($tags.models | ForEach-Object { $_.name })
$missingModels = @($profile.required_ollama_models | Where-Object { $_ -notin $installed })
if ($missingModels.Count) { throw "Missing required Ollama model(s): $($missingModels -join ', ')" }
Write-Host 'Owner-machine prerequisites passed.' -ForegroundColor Green
