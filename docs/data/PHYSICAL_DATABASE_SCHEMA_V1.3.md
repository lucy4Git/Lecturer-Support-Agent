# Physical Database Schema v1.3

## Schema boundaries

| PostgreSQL schema | Responsibility |
|---|---|
| `tenant` | Institutions, configurable organisational units, terminology, settings, academic periods |
| `iam` | Global identities, tenant memberships, independent roles, permissions, assignments, scopes |
| `academic` | Qualifications, programmes, modules, offerings, outcomes, lecturer/coordinator/moderator assignments, workloads |
| `ingestion` | Bulk upload batches and item processing state |
| `content` | Logical documents, immutable versions, storage objects, relationships, classifications |
| `conversation` | One unified conversation, messages, attachments, generated outputs and revisions |
| `ai` | AI requests and provider/model execution evidence |
| `source` | Genuine sources, retrievals, citations, claim links, verification results |
| `review` | External access, invitations, review assignments, approval workflows and actions |
| `audit` | Append-only audit, security, and outbox events |
| `privacy` | Retention and disposition rules |

## Design rules

- PostgreSQL is authoritative for records and relationships.
- Binary files are stored in versioned object storage, not database bytea columns.
- Every tenant-owned table contains an indexed `tenant_id`.
- Global users allow one person to hold memberships in multiple institutions.
- Institution Administrator and Head of Department are separate role records.
- Every assignment has effective dates and history instead of destructive replacement.
- A logical document points to a current version while every prior version remains retained.
- Generated AI outputs use the same append-only revision principle.
- Citations can be displayed only when linked to an actual retrieval record.
- External access is bounded by actions, resource scope, start, expiry, and audit history.

## Concurrency and consistency

Document updates lock the logical document row before allocating a version
number. A tenant/document/version unique constraint provides a second line of
protection. Exact file duplicates are recorded as duplicate events and point to
the existing version rather than creating wasteful identical binary copies.
Changed files always create a new version.

## Seed data

The seed creates two fictional institutions with deterministic UUIDs. Each has a
faculty, department, academic period, IoT demonstration module, module offering,
and synthetic users. This data exists only to test tenant isolation and role
behaviour; it is not training data.
