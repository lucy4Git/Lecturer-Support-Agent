# CLAUDE.md — Binding Implementation Instructions

Claude is the primary implementation agent.

## Mandatory read order

1. `PROJECT_CONSTITUTION.md`
2. `docs/blueprints/LECTURER_SUPPORT_AGENT_MASTER_BLUEPRINT.md`
3. `docs/requirements/FUNCTIONAL_REQUIREMENTS.md`
4. `docs/requirements/ROLE_PERMISSION_MATRIX.md`
5. `docs/architecture/SYSTEM_ARCHITECTURE.md`
6. `docs/data/CONTENT_VERSIONING_AND_PROVENANCE.md`
7. `docs/ux/UNIFIED_AI_WORK_AREA.md`
8. Relevant ADRs and PlantUML diagrams

## Absolute constraints

- Keep this a standalone Lecturer Support Agent.
- Preserve one unified ChatGPT-style work area.
- Do not create separate artifact or admin applications.
- Keep Institution Administrator and Head of Department independent.
- Never destructively replace uploaded study material.
- Never fabricate sources, institutional rules, compliance claims, or validation evidence.
- Do not expose model or agent selection to ordinary users.

## Implementation and live-preview workflow

For each vertical slice: identify requirement IDs; inspect architecture and existing code; implement production-quality behaviour; add unit/integration/E2E/security/accessibility tests; run lint, type checks, migrations and tests; launch live preview; log in as every affected role; demonstrate each UI/UX change at desktop, tablet and mobile breakpoints; test loading, empty, success, validation, permission-denied, failure and recovery states; fix issues immediately; update documentation, diagrams, traceability and changelog; then report commands, changed files, test results, preview evidence, fixes and remaining approved limitations.

A UI/UX checkpoint is incomplete without visible preview evidence.


## v1.5 audit entry condition

Before modifying v1.5, run the consolidated owner-machine validation in `docs/operations/V1.5_OWNER_MACHINE_VALIDATION.md`. Treat PostgreSQL, authentication, RLS, conversation persistence, Crossref retrieval, Ollama/cloud generation, provider fallback, Next.js build, browser preview, source cards, and live API behaviour as unverified until evidence is produced. Audit first, correct all failures, and do not report a checkpoint complete without live preview evidence for every affected role and response state.

Claude must preserve the provider-neutral contracts under `services/api/app/ai/`, the generic-by-default response principle, local-only restricted routing when configured, and the citation integrity rule that a displayed citation must originate from a retrieval associated with the same AI request.


## v1.6 mandatory audit focus

Before modifying v1.6, validate ZIP safety, extraction honesty, immutable versions, Qdrant tenant filters, PostgreSQL defence-in-depth access checks, institutional source provenance, attachment permissions, and the unified upload UI through live preview. Do not report this checkpoint complete without owner-machine evidence.


## v1.7 mandatory audit focus

Before modifying v1.7, complete `docs/operations/V1.7_OWNER_MACHINE_VALIDATION.md`. Validate module-assignment scoping, immutable context snapshots, output version history, academic workflow permissions, assessment-safety blockers, student-copy sanitisation, export object isolation, browser behaviour and responsive accessibility. Institution Administrator must not acquire academic approval authority by default. Do not report this checkpoint complete without live preview evidence and runtime database/storage tests.


## v1.8 mandatory audit focus

Before modifying v1.8, complete `docs/operations/V1.8_OWNER_MACHINE_VALIDATION.md`. Validate sealed pack hashes, exact-version pinning, task-assignee checks, external grant action/resource/time enforcement, grant revocation and expiry, immutable submissions, blocking-finding responses, correction rounds, formal-decision separation, scoped departmental dashboards and inline review UX for every affected role. Institution Administrator must not acquire academic review-decision authority. Do not report completion without live preview, migration, RLS and negative-access evidence.


## v1.9 implementation checkpoint

Departmental teaching plans, delivery sessions, module readiness, workload activities, academic calendar events, lecturer handovers and attention-first dashboards are implemented in source. Treat all live infrastructure and browser behaviour as **owner-machine validation pending**. Do not report this checkpoint as runtime-complete until migrations, RLS, seeded roles, browser workflows and responsive live preview are tested and evidence is recorded.


## v2.0 mandatory entry gate

Before changing any feature, read `VALIDATION_STATUS.md` and audit the latest owner-machine report created by `scripts/validation/Invoke-ConsolidatedOwnerValidation.ps1`. Do not accept source presence as runtime evidence. Correct every failed migration, RLS, storage, provider, browser, role, responsive or accessibility check; rerun the full gate; and include preview screenshots for every affected role. Claude may begin new implementation only after the owner explicitly approves the corrected validation result.


## v2.1 mandatory audit focus

Before changing v2.1, run the consolidated owner-machine gate and validate migration `20260725_0007`, governance-schema RLS, cross-tenant and cross-user search denial, inaccessible-file filtering, immutable saved-version pointers, recipient-only notifications, keyboard navigation, appearance, loading/empty/error states, and desktop/tablet/mobile live previews. Search, Library, Files, Saved outputs and Notifications must remain views inside the one unified work area; do not introduce a separate artifact application.

## v2.2 mandatory audit focus

Before changing v2.2, run the consolidated owner-machine gate and validate migration `20260726_0008`, the `analytics` schema, RLS for all eight v2.2 tables, personal versus department versus institution analytics, AI provider allow/deny and local-only behaviour, daily usage ledger accuracy, report checksums, Institution Administrator-only Audit Centre, secret-reference-only settings, and desktop/tablet/mobile live previews. Insights, Reports, Audit centre and Platform settings must remain views in the unified application; do not create a separate analytics or administration application.


## v2.4 mandatory audit focus

Before changing v2.4, validate migrations `20260726_0009` and `20260726_0010`, restriction of `lsa_worker`, operations/governance/privacy row-level security, scheduled-job enqueueing, worker leases, idempotency, retries and dead letters. Audit every connected handler for tenant context, immutable evidence, safe failure and truthful completion: ingestion, export, report generation, audit export, notification delivery, outbox publication, external-access expiry and retention. Confirm that unsupported delivery channels are blocked rather than reported as delivered, retention is dry-run or reversible-only, and backup/restore jobs remain operator-controlled until live evidence exists. Also validate upload malware scanning, request limits, rate limiting, metrics, readiness, log redaction, deployment security, onboarding data and synthetic labels. Institution Administrator and Head of Department must remain independent.


## v2.5 mandatory audit focus

Before modifying v2.5, run the consolidated owner-machine gate and validate migration `20260726_0011`, all 124 tables, account challenge secrecy, password-reset session revocation, TOTP/recovery-code single use, MFA secret encryption, OIDC PKCE/state/nonce/JWKS/issuer/audience/redirect controls, explicit federated account linking, tenant-scoped integration staging, secret-reference-only configuration, legal holds, second approval, exact object/vector deletion, backup tenant boundaries, manifest hashes and truthful restore-drill status. Confirm that real-source acquisition obeys recorded rights, evaluation data remains separated, PWA caching excludes protected responses, and legal templates are not represented as approved legal advice. Live evidence is mandatory before production or commercial-readiness claims.
