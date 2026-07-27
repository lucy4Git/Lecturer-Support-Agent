# Database Architecture

## 1. Architecture goals

The database platform must be robust, efficient, auditable and safe for multiple institutions. It must support high-volume conversations, bulk files, immutable versions, exact and semantic search, source evidence, departmental workflows and future analytics without weakening tenant isolation.

## 2. Polyglot persistence with one authoritative record

### PostgreSQL — system of record
Use PostgreSQL for identities, tenants, organisation hierarchy, roles, permissions, modules, assignments, conversations, artifact metadata, content identities, versions, upload batches, sources, citations, review workflows, audit events and model executions.

### Object storage — immutable binary objects
Use S3-compatible object storage for uploaded and generated files. Enable object versioning, server-side encryption, checksums, lifecycle policies and tenant-scoped prefixes or buckets.

### Search index — exact and faceted retrieval
Use an index such as OpenSearch/Elasticsearch or PostgreSQL full-text search initially. Support keyword search, filters, language analysis, academic period, document type and source facets.

### Vector index — semantic retrieval
Use a vector service such as Qdrant or an approved alternative. Every point contains tenant, scope, content version, sensitivity, visibility and effective-date metadata. Query filters are mandatory and applied server-side.

### Redis — ephemeral acceleration
Use Redis for sessions, rate limits, distributed locks, background-job state, idempotency and short-lived cache. Redis is never the authoritative location for academic records.

### Event/queue layer
Use a durable broker or transactional outbox for ingestion, indexing, notifications and audit projections. Do not rely on fire-and-forget events.

## 3. Data zones

1. **Quarantine:** untrusted uploads, no retrieval access.
2. **Raw:** immutable originals and acquisition snapshots.
3. **Normalized:** extracted text and standard metadata.
4. **Curated:** approved, quality-labelled content.
5. **Serving:** indexes and projections used by the application.
6. **Evaluation:** isolated benchmark and red-team data.
7. **Adaptation:** separately approved, rights-cleared training candidates.
8. **Archive:** retained but unavailable for normal operations.

Promotion between zones is an auditable state transition.

## 4. Core relational schemas

Recommended logical schemas:

- `iam`: users, identities, role definitions, assignments, delegations;
- `tenant`: institutions, unit types, units, terminology, configuration;
- `academic`: programmes, qualifications, modules, outcomes, allocations;
- `conversation`: threads, messages, inline artifacts and versions;
- `content`: content items, versions, relationships, classifications;
- `ingestion`: sessions, batches, items, processing attempts, errors;
- `source`: source records, evidence passages, claims and citations;
- `review`: moderation and external-review assignments/findings;
- `ai`: prompts, model registry, executions, tool calls, evaluations;
- `audit`: append-only security and business events;
- `privacy`: consent, legal holds, subject requests, retention actions;
- `analytics`: de-identified aggregate projections.

## 5. Tenant isolation

- Every tenant-owned row includes non-null `tenant_id`.
- Composite foreign keys include `tenant_id` to prevent cross-tenant references.
- PostgreSQL row-level security is enabled for tenant tables.
- Database sessions receive a verified tenant context from the authorisation service.
- Background jobs carry signed tenant and scope context.
- Search/vector queries require tenant filters; missing filter is a hard error.
- Object keys contain opaque tenant IDs, not names.
- Encryption keys may be tenant-specific for higher-assurance deployments.
- Cross-tenant public resources are copied or referenced through a separately governed public catalogue, not by bypassing isolation.

## 6. Organisational scopes

Use a closure table or materialised path for configurable hierarchies. Role assignments bind to a stable organisational unit and validity period. Permission evaluation resolves descendant or explicitly linked units. Changes to hierarchy create effective-dated relationship versions so historical actions remain interpretable.

## 7. Immutable content and provenance

`content_item` is the conceptual identity. `content_version` is append-only and references the object checksum and storage version. `content_relationship` records derived-from, supersedes, alternate, duplicate, translated-from, approved-copy and local-adaptation links. `canonical_pointer` is mutable only through a governed event and never changes historical versions.

## 8. Source and citation integrity

A generated claim references one or more `source_evidence` records. Evidence contains the actual retrieved passage, location, retrieval event, source version and support judgement. The UI may display a citation only after a verification status is recorded. Generated bibliographic strings are not accepted as evidence.

## 9. Performance design

- UUIDv7 or time-sortable opaque identifiers where supported.
- Composite indexes start with `tenant_id` for tenant tables.
- Partition high-volume audit, message, execution and event tables by time and, where necessary, tenant group.
- Use covering indexes for common listing queries.
- Store large text/binary outside transactional rows.
- Use cursor pagination rather than large offsets.
- Cache only data with clear invalidation and sensitivity controls.
- Batch index updates asynchronously while exposing processing status.
- Maintain read replicas for reporting without weakening consistency requirements.
- Use connection pooling and bounded background concurrency.

## 10. Reliability

- ACID transactions for metadata and permission changes.
- Transactional outbox for external events.
- Idempotency keys for uploads and API commands.
- Checksum verification from client to object store.
- Point-in-time database recovery and versioned object recovery.
- Tested backup, restore and tenant-level export procedures.
- Dead-letter queues with replay controls.
- Schema migrations are backward-compatible and rehearsed.

## 11. Security

- Encryption in transit and at rest.
- Least-privilege database roles per service.
- Secrets outside source control.
- Parameterised queries and ORM safeguards.
- Tamper-evident audit chains for sensitive events.
- Field-level encryption or tokenisation for highly sensitive identifiers.
- No raw confidential document content in logs.
- Query and export limits to reduce exfiltration risk.

## 12. Data quality constraints

Database constraints enforce tenant consistency, non-overlapping active assignments where required, valid version sequence, immutable checksum fields, allowed state transitions, source-evidence linkage and external-access expiry. Application validation supplements but does not replace database integrity.

## 13. Initial implementation recommendation

Start with PostgreSQL, S3-compatible object storage, Qdrant, Redis and PostgreSQL full-text search. Introduce a dedicated search engine only after measured scale or search requirements justify it. This reduces operational complexity while preserving an upgrade path.

## 14. Database acceptance tests

- cross-tenant insert and query attempts fail;
- a new upload never mutates an earlier version;
- duplicate decisions preserve both provenance chains;
- expired external access is denied immediately;
- bulk upload is resumable and idempotent;
- point-in-time restore recovers relational and object references;
- source cards cannot be produced without evidence records;
- representative listing and search queries meet latency targets under load.
