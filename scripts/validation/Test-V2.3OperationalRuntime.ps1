[CmdletBinding()]
param(
    [string]$ApiBaseUrl = 'http://localhost:8000',
    [string]$ComposeFile = 'compose.yaml',
    [switch]$SkipWorkerProbe
)
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
$Root = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
Set-Location $Root

function Assert-Condition([bool]$Condition, [string]$Message) {
    if (-not $Condition) { throw $Message }
}

Write-Host 'Checking Docker Compose services...'
$services = docker compose -f $ComposeFile ps --services --status running
Assert-Condition ($LASTEXITCODE -eq 0) 'Docker Compose service inspection failed.'
foreach ($required in @('postgres','redis','minio','qdrant')) {
    Assert-Condition ($services -contains $required) "Required service is not running: $required"
}

Write-Host 'Checking API health and dependency readiness...'
$health = Invoke-RestMethod "$ApiBaseUrl/health" -TimeoutSec 15
Assert-Condition ($health.status -eq 'ok') 'API health endpoint did not return ok.'
try {
    $ready = Invoke-RestMethod "$ApiBaseUrl/ready" -TimeoutSec 30
} catch {
    throw "API readiness failed: $($_.Exception.Message)"
}
Assert-Condition ($ready.status -eq 'ready') 'API readiness endpoint did not report ready.'

if ($env:METRICS_ENABLED -ne 'false') {
    Assert-Condition (-not [string]::IsNullOrWhiteSpace($env:METRICS_TOKEN)) 'METRICS_TOKEN is required for the protected metrics probe.'
    $headers = @{ 'X-Metrics-Token' = $env:METRICS_TOKEN }
    $metrics = Invoke-WebRequest "$ApiBaseUrl/metrics" -Headers $headers -TimeoutSec 15 -UseBasicParsing
    Assert-Condition ($metrics.StatusCode -eq 200) 'Protected metrics endpoint failed.'
    Assert-Condition ($metrics.Content -match 'lsa_http_requests_total') 'Expected LSA metrics were not emitted.'
}

Write-Host 'Checking worker database role...'
$roleSql = "SELECT rolname, rolsuper, rolcreaterole, rolcreatedb, rolbypassrls FROM pg_roles WHERE rolname = 'lsa_worker';"
$roleResult = docker compose -f $ComposeFile exec -T postgres sh -lc "psql -U \$POSTGRES_USER -d \$POSTGRES_DB -Atc \"$roleSql\""
Assert-Condition ($LASTEXITCODE -eq 0) 'Could not inspect lsa_worker.'
Assert-Condition ($roleResult -match '^lsa_worker\|f\|f\|f\|f$') 'lsa_worker is missing or has unsafe privileges.'

Write-Host 'Checking ClamAV TCP port when enabled...'
if ($env:MALWARE_SCAN_ENABLED -eq 'true') {
    $clam = Test-NetConnection -ComputerName 'localhost' -Port 3310 -WarningAction SilentlyContinue
    Assert-Condition $clam.TcpTestSucceeded 'ClamAV is enabled but port 3310 is unavailable.'
}

if (-not $SkipWorkerProbe) {
    Write-Host 'Running one safe worker claim cycle...'
    python -m services.worker.main --once
    Assert-Condition ($LASTEXITCODE -eq 0) 'The one-cycle background worker probe failed.'
}

Write-Host 'v2.3 operational runtime probes passed.' -ForegroundColor Green
