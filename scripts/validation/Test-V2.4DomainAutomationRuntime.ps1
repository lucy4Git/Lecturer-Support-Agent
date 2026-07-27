[CmdletBinding()]
param([string]$ApiBaseUrl='http://localhost:8000/api/v1')
$ErrorActionPreference='Stop'
Write-Host 'v2.4 runtime validation requires an authenticated Institution Administrator browser/API session.' -ForegroundColor Yellow
Write-Host 'Validate the following in order:'
Write-Host '1. Run migration 20260726_0010 and confirm 107 SQLAlchemy tables.'
Write-Host '2. Start the lsa_worker role and confirm operations.enqueue_due_scheduled_jobs executes without BYPASSRLS.'
Write-Host '3. Create a 60-second test schedule and confirm one idempotent background job is materialised.'
Write-Host '4. Emit a notification and confirm governance.notification_deliveries records in_app=delivered.'
Write-Host '5. Create temporary external access, move its expiry into the past, and confirm automatic expiry plus notification.'
Write-Host '6. Run retention in dry-run mode and confirm no resources change.'
Write-Host '7. Run reversible retention and confirm only archive/expire actions occur; no hard delete.'
Write-Host '8. Generate a report and audit export through the worker and verify SHA-256 results.'
Write-Host '9. Process one document ingestion and one output export using live MinIO, Qdrant and Ollama.'
Write-Host '10. Confirm backup and restore-drill jobs still fail honestly until destinations are configured.'
