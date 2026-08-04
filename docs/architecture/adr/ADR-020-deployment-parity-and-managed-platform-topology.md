# ADR-020 — Deployment parity and managed-platform topology

**Status:** Accepted  
**Release:** v2.6.0

## Decision

The Lecturer Support Agent is deployed from one validated source revision using:

- Vercel for the Next.js web application;
- Render for the FastAPI API, worker, Redis-compatible temporary state, and ClamAV;
- Neon for PostgreSQL;
- private S3-compatible object storage with object versioning;
- Qdrant Cloud for tenant-filtered vectors;
- protected SMTP and AI-provider credentials supplied through deployment secret stores.

Staging and production must use the same application source, Alembic migration chain, role/permission catalogue, configuration contracts, and approved data manifests as the validated local system. Environment values and data are separate.

## Mandatory parity rule

Deployment is not accepted merely because public URLs respond. Acceptance requires a checksum-verified comparison of:

- application release and Git revision;
- Alembic head and application schema inventory;
- roles, permissions, and approved reference data;
- approved PostgreSQL tenant data;
- logical object keys, sizes, checksums, and deployed version identifiers;
- Qdrant vector configuration, tenant payloads, and document-version relationships;
- all eight staging role workflows.

Redis is always initialised clean and is never migrated from local development.

## Data boundaries

Approved data is exported only from a source explicitly marked as approved and containing only allowlisted tenant identifiers. Local secrets, sessions, password hashes, reset or invitation tokens, MFA material, temporary jobs, model binaries, caches, and unapproved institutional information are excluded.

Production does not run demonstration seeding. Temporary production verification accounts are created through the real invitation workflow and disabled after acceptance.

## Consequences

- The same release can be promoted through staging and production without redesign.
- Local-to-deployed parity is auditable and repeatable.
- Object-store version identifiers may differ between providers, so logical checksums and an applied version mapping are verified.
- Qdrant may be rebuilt from approved deployed document versions when that is safer than copying a local collection.
- Deployment requires protected vendor resources and secret entry, but no further core application implementation.
