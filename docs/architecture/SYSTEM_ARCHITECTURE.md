# System Architecture

## Style

A modular service-oriented architecture supports a responsive web/PWA, future mobile clients and institutional integrations. Early delivery may deploy selected modules as a modular monolith if domain boundaries and contracts remain explicit.

## Experience layer

Responsive web/PWA; future mobile clients; API gateway/BFF; real-time response streaming; adaptive role-aware actions; unified conversation and inline artifact rendering.

## Identity and institution

Identity/session, tenant, configurable organisational hierarchy, independent role assignment, RBAC plus scoped/context attributes, policy authorization and temporary external access.

## Lecturer-support domains

Conversation/artifacts, teaching content, assessment, course assignment/workload, programme/module alignment, moderation/review, notification and export.

## AI and trust

Intent/risk classification, provider-neutral model gateway, prompt/evaluation registry, source discovery, source verification, claim-citation mapping, safety, academic integrity and unsupported-claim validation.

## Content platform

Resumable bulk ingestion, malware scanning, metadata extraction/classification, exact/probable duplicate detection, stable content identity, immutable versions, provenance, canonical pointers, object storage, relational metadata, full-text search and vector indexes.

## Cross-cutting platform

Audit, analytics, usage/cost metering, feature flags, configuration, secrets/KMS, logs, metrics, traces, alerting, backup, disaster recovery, retention and legal hold.

## Consistency and security

Relational transactions govern identities, roles, metadata, versions, assignments and reviews. Large objects remain immutable. Outbox events synchronize indexes and workers. Tenant and scope derive from authenticated server context, never trusted client fields. Assessment bytes may use stricter encryption and access policies.

See `docs/architecture/uml/architecture/01_system_architecture.plantuml`.

## v2.1 workspace composition

A tenant-aware Workspace API composes authorised search, Library, Files, saved-output pointers, notifications, personal summaries, and role navigation. It queries existing bounded domains rather than copying their records into a second datastore. Search results and saved references retain canonical resource and version identifiers, while the Next.js backend-for-frontend keeps access and refresh credentials in HTTP-only cookies.
