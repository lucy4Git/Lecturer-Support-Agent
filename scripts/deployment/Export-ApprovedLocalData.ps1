[CmdletBinding()]
param(
    [string]$OutputDirectory = "runtime/deployment/approved-data",
    [switch]$IncludeAuditEvidence
)
$ErrorActionPreference = "Stop"
if (-not $env:MIGRATION_DATABASE_URL) { throw "MIGRATION_DATABASE_URL is required." }
if (-not $env:APPROVED_TENANT_IDS) { throw "APPROVED_TENANT_IDS is required." }
if ($env:EXPORT_SOURCE_APPROVED -notin @('true','1','yes')) { throw "Set EXPORT_SOURCE_APPROVED=true only after formal source approval." }
python scripts/deployment/validate_approved_export_source.py
if ($LASTEXITCODE -ne 0) { throw "Approved export-source preflight failed." }
$url = $env:MIGRATION_DATABASE_URL -replace '^postgresql\+psycopg://', 'postgresql://'
New-Item -ItemType Directory -Force -Path $OutputDirectory | Out-Null
$stamp = Get-Date -Format "yyyyMMdd_HHmmss"
$dump = Join-Path $OutputDirectory "lsa-approved-data-$stamp.dump"
$manifest = "$dump.sha256.json"
$schemas = @('tenant','iam','academic','ingestion','content','conversation','ai','source','review','privacy','governance','analytics','operations')
$args = @($url, '--format=custom', '--data-only', '--no-owner', '--no-privileges', '--file', $dump)
foreach ($schema in $schemas) { $args += @('--schema', $schema) }
# Secrets, active sessions, reset/invitation tokens, transient queues and local evidence never migrate.
$excluded = @(
  'iam.password_credentials','iam.authentication_sessions','iam.account_challenges',
  'iam.mfa_devices','iam.mfa_recovery_codes','iam.user_invitations',
  'governance.outbound_messages','operations.background_jobs','operations.background_job_attempts',
  'operations.dead_letter_jobs','operations.job_schedules','operations.backup_runs',
  'operations.restore_drills','operations.dataset_acquisition_runs','operations.integration_sync_runs'
)
if (-not $IncludeAuditEvidence) { $excluded += @('audit.audit_events','audit.security_events','audit.audit_outbox') }
foreach ($table in $excluded) { $args += "--exclude-table-data=$table" }
& pg_dump @args
if ($LASTEXITCODE -ne 0) { throw "pg_dump failed with exit code $LASTEXITCODE" }
$hash = (Get-FileHash $dump -Algorithm SHA256).Hash.ToLower()
@{
  schema_version = '1.0'; created_at = (Get-Date).ToUniversalTime().ToString('o');
  dump_file = (Split-Path $dump -Leaf); sha256 = $hash; excluded_tables = $excluded;
  approval_required = $true; includes_secrets = $false
} | ConvertTo-Json -Depth 5 | Set-Content -Encoding utf8NoBOM $manifest
Write-Host "Approved-data candidate created: $dump"
Write-Host "Review and formally approve its manifest before import."
