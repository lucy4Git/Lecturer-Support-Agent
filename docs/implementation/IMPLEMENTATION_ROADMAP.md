# Implementation Roadmap

0. Governance, repository, requirements, UML, ADRs and evaluation foundation.
1. Tenant, identity, configurable hierarchy, independent roles and audit.
2. Responsive/PWA unified work area, streaming, source cards, inline artifacts and accessibility.
3. Provider gateway, generic AI, source discovery/verification and hallucination controls.
4. Lesson, practical, case study, quiz, test, assignment, exam, rubric and marking-guide capabilities.
5. Resumable bulk ingestion, scanning, classification, duplicates, immutable versions and provenance.
6. Course assignment, workload/readiness, coordinator alignment and departmental handover.
7. Moderation, temporary external review, findings, expiry/revocation and review uploads.
8. Exports, integrations, notifications, analytics, observability, security, performance and DR.
9. Pilot evaluation, support operations, legal/privacy package and commercial readiness.

## Checkpoint status

- Repository, data strategy, multi-provider AI and model-readiness foundation: complete through v1.2.
- Physical multi-tenant data and database foundation: implemented in v1.3; local infrastructure integration tests remain owner-machine validation.
- Production authentication, identity administration, configurable HEI structure, HOD operations, and the first unified role-aware shell: implemented in v1.4; owner-machine runtime and live-preview validation remain pending.
- Unified AI request execution, provider routing, generic responses, source discovery, citation integrity, and inline output rendering: implemented in v1.5; owner-machine runtime and live-preview validation remain pending.
- Contextual ingestion and authorised retrieval: implemented in v1.6; owner-machine validation pending.
- Production teaching-output workflows, inline versioning, module context, assessment safety and exports: implemented in v1.7; owner-machine validation pending.
- Assignment-specific moderation, external review, findings, decisions, corrections and departmental oversight: implemented in v1.8; owner-machine validation pending.
- Departmental teaching plans, delivery monitoring, module readiness, workload, academic calendar, lecturer handover and operational dashboards: implemented in v1.9; owner-machine validation pending.


## Completed checkpoint: v1.6

Contextual bulk upload, safe ingestion, immutable version processing, authorised institutional retrieval, Qdrant indexing, governed embeddings and source-aware attachments are implemented in source. Consolidated owner-machine validation remains mandatory before Claude begins.


## Completed checkpoint: v1.7

Production teaching-output workflows, authorised module context, inline immutable editing, academic lifecycle controls, assessment safety and export generation are implemented in source without creating a separate artifact workspace. Consolidated owner-machine validation remains mandatory before Claude begins.


## Completed checkpoint: v1.8

Assignment-specific review cycles, sealed exact-version review packs, internal/external reviewer tasks, findings, immutable submissions, formal decisions, correction rounds, grant revocation/expiry and departmental oversight are implemented in source without creating a separate moderation portal. Consolidated owner-machine validation remains mandatory before Claude begins.


## v1.9 — Departmental Teaching Operations
Implemented teaching plans, delivery monitoring, readiness, workload, academic calendar, handover continuity, and operational dashboards. Runtime validation is deferred to the consolidated owner-machine checkpoint.


## v2.0 — Consolidated validation and Claude handover readiness

Implemented one cumulative owner-machine validation command, secret-safety checks, service probes, live role previews, responsive screenshots, evidence redaction, failure triage and a fail-closed runtime acceptance report. Actual owner-machine execution remains the next mandatory action.


## v2.1 — Commercial unified workspace

Implemented unified Search, Library, Files, Saved outputs, Notifications, role-aware navigation, immutable saved-version pointers, authorised server-side search, responsive resource views, keyboard search, and appearance controls. The consolidated owner-machine gate remains pending and now includes v2.1 validation.

## v2.2 — Scoped analytics and commercial governance

Implemented role-scoped teaching insights, immutable analytics snapshots and reports, multi-provider AI usage policy, user-specific daily usage ledgers, an Institution Administrator Audit Centre, versioned non-secret platform settings, and unified Insights/Reports/Audit/Settings views. The consolidated owner-machine gate remains pending and now includes v2.2 migration, RLS, provider-governance, reporting and browser validation.


## v2.3 — Production hardening and operational readiness

Implemented durable PostgreSQL-leased jobs, restricted worker-role access, retries/dead letters, request hardening, rate limiting, ClamAV integration, structured observability, dependency readiness, backup/restore automation, production container/Kubernetes foundations, CI gates, deterministic synthetic fixtures, and institution-onboarding validation. Live domain handlers, infrastructure, restore drills, performance, security and pilot evidence remain governed runtime checkpoints.


## v2.4 — Durable domain automation

Implemented real queue handlers for in-app notification delivery, outbox publication, automatic external-access expiry, reversible retention, analytics reports, audit exports, document ingestion, and teaching-output exports. Added governed interval schedules, delivery and retention evidence, and an Institution Administrator platform-operations view. Backup and restore-drill execution remains an owner-machine integration gate. Consolidated runtime validation remains mandatory before Claude audit or production-readiness claims.


## v2.5 — Completion gap closure and commercial release preparation

Implemented account recovery, email verification, TOTP MFA, OIDC SSO, academic-system adapters, staged enterprise synchronisation, outbound email, legal holds, governed deletion, connected tenant-scoped backup/restore-drill execution, metadata acquisition with rights gates, feedback/evaluation capture, PWA foundations, legal/commercial templates and pilot readiness. Production credentials, live institution integrations, full-text rights approval, deployment, legal approval and owner-machine evidence remain governed completion gates.
