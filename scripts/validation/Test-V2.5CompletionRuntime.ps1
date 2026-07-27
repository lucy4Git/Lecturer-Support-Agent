[CmdletBinding()]
param([string]$ApiBaseUrl='http://localhost:8000/api/v1')
$ErrorActionPreference='Stop'
Write-Host 'v2.5 completion runtime validation requires configured synthetic/test tenants and authorised accounts.' -ForegroundColor Yellow
Write-Host '1. Verify migration 20260726_0011 and 124 registered tables.'
Write-Host '2. Complete password reset and prove prior sessions are revoked.'
Write-Host '3. Enrol TOTP, reject an incorrect code, accept a correct code, and consume a recovery code only once.'
Write-Host '4. Validate OIDC PKCE/state/nonce, issuer, audience, signature, redirect allowlist and explicit account linking.'
Write-Host '5. Test a non-production Canvas/Moodle/OneRoster connection and confirm staged, idempotent mappings.'
Write-Host '6. Deliver an invitation/password-reset email through the configured test SMTP server and inspect redacted logs.'
Write-Host '7. Prove legal holds block deletion; then approve a synthetic document-version deletion and verify PostgreSQL/MinIO/Qdrant evidence.'
Write-Host '8. Run a tenant backup outside the repository, verify the manifest, and perform an isolated restore drill.'
Write-Host '9. Acquire approved OpenAlex/Crossref metadata and verify object version, checksum and rights metadata.'
Write-Host '10. Install the PWA, test offline fallback, accessibility, mobile behaviour and reconnect handling.'
