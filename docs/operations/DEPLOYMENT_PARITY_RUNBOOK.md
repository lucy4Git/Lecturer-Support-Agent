# Mandatory deployment parity and approved-data migration runbook

This runbook is a non-negotiable acceptance gate.

## Principle

Staging and production must be created from the same validated application version, Alembic chain, role/permission catalogue, configuration contracts, and approved data manifests as the local system. Environment secrets are intentionally different.

## Relational data

1. Create a local backup/restore point.
2. Use a dedicated local migration-source database that contains only the approved tenant(s); do not export from a mixed or production database.
3. Set `MIGRATION_DATABASE_URL`, `APPROVED_TENANT_IDS`, and `EXPORT_SOURCE_APPROVED=true` in the process environment.
4. Run `Export-ApprovedLocalData.ps1`; its preflight fails if any unapproved tenant is present.
5. Review the excluded-table list and data content with the data owner.
6. Record formal approval and SHA-256.
7. Run Alembic against the empty destination.
8. Import the approved dump before staging demo credentials are generated.
9. Set a strong random `SEED_DEMO_PASSWORD` in Render, enable `ENABLE_DEMO_SEED=true` for one staging deploy, then disable it again. This creates/refreshes the eight synthetic accounts without copying local password hashes.
10. Never run the demo seed in production.

The export excludes password hashes, sessions, MFA records, reset/invitation tokens, message bodies, job queues, backup metadata, and local runtime evidence.

## Object storage

1. Set source/destination S3-compatible environment variables.
2. Set `APPROVED_TENANT_IDS`.
3. Run `migrate_object_versions.py`.
4. Verify every SHA-256 and destination version identifier.
5. Apply the approved mapping to PostgreSQL using `apply_storage_version_mapping.py --approved`.
6. Verify that each `content.storage_objects` row points to an existing destination object version.

## Qdrant

The preferred method is to re-index from deployed, authorised document versions using the configured production embedding model. When an exact vector transfer is approved, run `migrate_qdrant.py` with an approved tenant allowlist and verify point IDs, tenant payload, document-version IDs, vector size, and collection configuration.

## Redis

Do not migrate Redis. Start it clean. PostgreSQL is authoritative for sessions, jobs, grants, notifications, and audit records; Redis contains only temporary operational state.

## Parity evidence

Generate:

```powershell
python scripts/deployment/create_parity_manifest.py --label local-approved --output runtime/deployment/local.json
python scripts/deployment/create_parity_manifest.py --label staging --output runtime/deployment/staging.json
python scripts/deployment/verify_parity.py runtime/deployment/local.json runtime/deployment/staging.json
```

The verifier compares logical S3 object versions by key, size, and SHA-256 rather than provider-specific version IDs, and compares Qdrant payload identity/configuration rather than collection names. For production, compare the schema/catalogue contract and only the specifically approved production data manifest. Synthetic staging user counts are not expected to match production.

## Required functional validation

- login, logout, refresh and role selection;
- invitation acceptance and request-access review;
- password recovery, email verification and MFA;
- all eight staging roles;
- tenant isolation and direct-object denial;
- upload, immutable versions, extraction and retrieval;
- AI generation and source integrity;
- moderation, external expiry/revocation and review decisions;
- exports, background jobs, notifications and audit evidence;
- backup and isolated restore drill.

## Acceptance statement

A deployment is not complete merely because the URLs respond. It is complete only after the redacted parity report, role workflows, data checksums, backup/restore evidence, and security test results are approved.
