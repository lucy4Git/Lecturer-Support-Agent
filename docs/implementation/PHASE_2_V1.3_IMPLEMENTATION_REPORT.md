# Phase 2 v1.3 Implementation Report

**Checkpoint:** Physical Data and Database Foundation  
**Status:** Implemented and statically validated  
**Scope:** Backend foundation only; no claim of production deployment or completed commercial UI

## What was implemented

Version 1.3 converts the approved data architecture into an executable foundation:

- 53 SQLAlchemy 2 physical tables across 11 PostgreSQL schemas;
- Alembic initial migration and schema creation;
- fail-closed tenant row-level security for all tenant-owned tables;
- independent roles and explicit permissions;
- configurable organisational hierarchy and closure table;
- academic periods, qualifications, programmes, modules, offerings, outcomes, assignments, and workloads;
- single and bulk upload records;
- immutable object and document versions;
- source, retrieval, citation, claim-support, and verification records;
- unified conversation, AI routing, and generated-output version records;
- temporary external access and assigned review tasks;
- append-only audit, security, workflow, retention, and outbox records;
- S3/MinIO, Qdrant, and Redis integration contracts;
- FastAPI endpoints for documents, bulk uploads, lecturer assignments, and external access;
- synthetic two-tenant seed data; and
- Windows PowerShell setup, migration, seed, isolation-test, reset, and safe-archive scripts.

## Why this phase precedes the UI

The unified work area will depend on stable identities, scopes, modules, documents,
conversations, sources, and audit evidence. Implementing these contracts first
prevents the interface from encoding temporary assumptions about a single
institution or role.

## How tenant isolation works

1. Trusted request identity creates a tenant/user/role context.
2. The API opens a database transaction.
3. Transaction-local PostgreSQL settings are applied.
4. RLS policies compare each row's `tenant_id` with the transaction tenant.
5. Role and scope checks narrow access further.
6. Qdrant searches add an immutable server-generated tenant filter.
7. MinIO keys are tenant and document-version scoped.

## Important limits

- Development header authentication is a temporary local mechanism, not a production identity solution.
- Database, MinIO, Qdrant, and Redis integration tests require the local containers to be running.
- Real institutional data and third-party datasets were not added.
- The initial Alembic migration creates the approved metadata in one baseline revision; later changes must use explicit incremental revisions.
- Background malware scanning, text extraction, OCR, and embedding workers are future phases.

## Acceptance evidence

- Python compilation: passed.
- SQLAlchemy metadata registration: 53 tables.
- PostgreSQL mock DDL compilation: 138 DDL statements.
- Unit tests: 10 passed.
- JSON seed catalogue: validated.
- PlantUML source structure: validated by repository validator.
- Secret-bearing `.env` remains excluded; safe `.env.example` retained.

## Next checkpoint

After owner review and a Claude audit, Phase 3 should implement authentication,
identity-provider integration, user onboarding, organisational administration,
and the first live unified-work-area slice against this foundation.
