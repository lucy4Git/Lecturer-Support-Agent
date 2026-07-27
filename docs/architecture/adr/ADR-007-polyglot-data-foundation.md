# ADR-007: Polyglot Data Foundation with PostgreSQL as Authority

- **Status:** Accepted
- **Date:** 2026-07-24

## Context

The platform must combine transactional academic records, large files, semantic
retrieval, and temporary high-speed state without weakening tenant isolation or
version evidence.

## Decision

Use:

- PostgreSQL for authoritative domain and audit records;
- MinIO/S3-compatible versioned object storage for binary content;
- Qdrant for tenant-filtered vectors; and
- Redis for disposable operational state.

PostgreSQL IDs and permissions remain the authority. Vector or cache entries
cannot grant access and cannot replace relational audit evidence.

## Consequences

### Positive

- each storage engine performs a suitable workload;
- immutable binary versions do not inflate PostgreSQL;
- semantic retrieval remains scalable;
- cache loss does not remove academic records; and
- source, version, and tenant provenance remain traceable.

### Trade-offs

- local development requires four services;
- backup and restore must coordinate multiple stores;
- background reconciliation is required for rare partial failures; and
- operational observability must cover every component.

## Rejected alternatives

- storing every file directly in PostgreSQL;
- using a vector database as the source of truth;
- using Redis for permanent access grants or audit history; and
- separate databases per faculty, which would prevent flexible institution structures and complicate institution-wide coordination.
