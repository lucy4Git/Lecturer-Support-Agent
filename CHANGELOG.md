# Changelog



## [2.5.0-rc4-gap-closure] - 2026-07-30

### Fixed (Gap Closure — All 8 Roles + Accessibility + Integration Tests)

- **Seed gap closed**: Added Module Coordinator, Programme Coordinator, External Moderator seed accounts with CoordinatorAssignment, ExternalAccessGrant, AssignedReviewTask, and Programme/ProgrammeModule records. All 8 roles are now browser-testable.
- **A-003 Muted text contrast (WCAG 1.4.3 Level AA)**: Darkened `--muted` from `#667085` (3.9:1 on white) to `#535d6e` (~5.8:1). All inline `#667085` hardcodes replaced with `var(--muted)`.
- **A-004 Nav icon accessibility**: Added `aria-label` and `title` attributes to all workspace nav buttons, providing tooltip text and screen-reader labels when labels are visually hidden in collapsed sidebar.
- **B-001 document_versioning flush ordering**: Inserted explicit `await session.flush()` after `storage_object` and after `version` to resolve `fk_documents_current_version` FK violation caused by SQLAlchemy's `use_alter=True` FK being excluded from flush dependency analysis.
- **T-001 Integration test conftest**: Created root `conftest.py` loading `.env` via `python-dotenv` and setting `WindowsSelectorEventLoopPolicy` on Windows, resolving ProactorEventLoop error and DATABASE_URL skip in `test_document_versioning.py`.
- **T-002 Test tenant UUID**: Corrected hardcoded tenant UUID in `test_document_versioning.py` to `stable_id("tenant:demo-north")`.
- **T-003 Test module scope**: Added `module_id` parameter to `create_version()` calls in test, matching the lecturer's access scope.
- **T-004 Tenant isolation count**: Updated `test_tenant_isolation.py` expected membership count from 5 to 8 to match new seed accounts.

### Live Preview Evidence (Session 3)

- All 8 roles browser-tested: Institution Administrator, Lecturer, Head of Department, Internal Moderator, External Reviewer, Module Coordinator, Programme Coordinator, External Moderator
- Breakpoints tested for all new roles: 375×812, 768×1024, 1280×800
- TypeScript: 0 errors; Unit: 151 passed; Integration: 94 passed (0 skipped)

## [2.5.0-rc3-live-preview] - 2026-07-30

### Fixed (Live Preview Validation)

- **A-001 Skip navigation link (WCAG 2.4.1 Level A)**: Added `.skip-nav` link as first element in `<body>` targeting `#main-content`. Keyboard users can now bypass sidebar navigation. Added `id="main-content"` to `<main>` in workspace shell and sign-in page.
- **A-002 Focus ring for interactive elements (WCAG 2.4.7 Level AA)**: Added global `:focus-visible { outline: 3px solid var(--accent); outline-offset: 2px; border-radius: 4px; }` to `globals.css`. Previously only `input` and `select` had focus styles.

### Live Preview Evidence

- Evidence directory: `runtime/validation/20260730_live_preview/`
- Roles tested in browser: Institution Administrator, Lecturer, Head of Department, Internal Moderator, External Reviewer (5 of 8)
- Breakpoints tested: 375×812, 768×1024, 1280×720, 1440×900
- AI generation confirmed: openai / gpt-4o-mini-2024-07-18
- TypeScript: 0 errors; Next.js build: 18 routes success; Unit: 151 passed; Integration: 93 passed


## [2.5.0-rc2-phases-f-l] - 2026-07-29

### Fixed (Phases F–L owner-machine validation)

- **J-001 Public password-reset paths**: `RequestContextMiddleware` now lists
  `/api/v1/auth/password-reset/`, `/api/v1/auth/email-verification/`, and
  `/api/v1/auth/sso/` in `PUBLIC_PATH_PREFIXES`. Previously these endpoints
  returned 401, blocking account recovery without authentication.
- **F-009 security cleanup**: `ReadinessService._safe_detail()` is now
  environment-aware. Production and staging return only a sanitised dependency
  name and correlation ID. Development returns the exception type plus a
  redacted message. Full exception detail is always written to the structured
  server logger. Nine unit tests verify production sanitisation.
- **L-007 FederatedIdentity assertion**: integration test corrected to assert
  `sso_connection_id` column (was checking incorrect names `provider`/`connection_id`).

### Added

- `tests/integration/test_phases_f_through_l.py`: 93-test integration suite
  covering Phases F through L (tenant isolation, storage, AI routing, citation
  integrity, core workflows, background jobs, enterprise foundations).
- `tests/unit/test_readiness_diagnostics.py`: 9 unit tests for production
  readiness-probe sanitisation.
- `pyproject.toml`: registered `slow` pytest marker.

### Infrastructure Findings

- **H-001 (owner-machine, not a code defect)**: qwen3:8b cannot be loaded on
  the owner machine — llama-server OOM (3.3 GB CPU buffer allocation fails).
  Embedding (nomic-embed-text-v2-moe) works correctly at 768 dimensions.
  AI routing source code, structured output, provider fallback, token recording
  and local-only enforcement are all present and tested at contract level.

### Test Counts

- Unit: 151 passed
- Integration: 92 passed, 1 skipped (H-001 infrastructure)
- Release validators: 13/13 PASS

## [2.5.0-rc1-owner-validation] - 2026-07-29

### Fixed (owner-machine validation)

- **F-009 Windows ProactorEventLoop**: `services/api/run_api.py` now passes
  `loop=asyncio.SelectorEventLoop` to `uvicorn.run()`. Uvicorn 0.49 forwards
  this as `loop_factory` to `asyncio.run()`, guaranteeing a `SelectorEventLoop`
  is created before any psycopg3 connection attempt. `main.py` retains the
  `WindowsSelectorEventLoopPolicy` guard as defence-in-depth. All four readiness
  probes (PostgreSQL, Redis, Qdrant, MinIO) now return healthy on Windows.
- **F-001/F-002/F-003 Next.js Suspense**: `accept-invitation`, `reset-password`
  and `sso/callback` pages extract `useSearchParams()` callers into child
  components wrapped in `<Suspense>`, unblocking the production build.
- **F-004 Forbidden-path loop logic**: validation scripts changed `break` to
  `continue` so `.git/` and `.next/` paths are skipped rather than erroring.
- **F-005 Windows cp1252 encoding**: all `.read_text()` calls in tests and
  validators now pass `encoding="utf-8"` explicitly.
- **F-006 v1.3 migration schema gap**: added `analytics`, `operations`,
  `governance` to the `SCHEMAS` tuple so all 14 schemas are created before
  `Base.metadata.create_all()` runs.
- **F-007 v1.8/v2.5 idempotent migrations**: replaced `op.add_column()` and
  `op.create_foreign_key()` with `ADD COLUMN IF NOT EXISTS` and conditional
  constraint SQL so migrations are safe on databases bootstrapped by `create_all`.
- **F-008 Health version string**: `routes/health.py` now returns `"2.5.0"`.
- **Route introspection**: all tests and validators use
  `app.openapi()["paths"].keys()` instead of `route.path for route in app.routes`
  (FastAPI 0.139 returns `_IncludedRouter` objects that have no `.path`).

### Added (owner-machine validation)

- `tests/unit/test_windows_event_loop.py` — 5 regression tests covering
  `WindowsSelectorEventLoopPolicy` installation, loop-type assertion, live async
  DB query on SelectorEventLoop, and uvicorn loop-factory acceptance.
- Qdrant collection `lecturer_support_documents` created during validation.
- `runtime/validation/` directory with timestamped evidence records.

### Status (owner-machine 2026-07-29)

- **Phases A–E validated**: static checks pass, all 11 migrations applied,
  124 tables, 14 schemas, RLS confirmed, all four readiness probes healthy,
  MinIO versioning confirmed, Qdrant collection created, Ollama generation model
  present. Unit suite: **142/142 pass**.
- **Approved limitation**: Ollama embedding model `nomic-embed-text-v2-moe`
  not yet pulled; run `ollama pull nomic-embed-text-v2-moe` before ingestion.
- **Phases F–L**: tenant isolation, AI providers, citation integrity, user
  workflows, background jobs and commercial foundations validation pending.

## [2.5.0] - 2026-07-26

### Added

- Password reset, email verification, TOTP MFA, encrypted device secrets, recovery codes and session revocation.
- OIDC Authorization Code with PKCE, state, nonce, discovery/JWKS validation, federated identities and explicit verified-email linking policy.
- Canvas, Moodle, OneRoster CSV/REST and governed generic REST adapters with staged sync runs and external-record mappings.
- Durable SMTP-backed outbound email, legal holds, two-person deletion approval, exact document-version deletion across PostgreSQL/MinIO/Qdrant, feedback and evaluation campaigns.
- OpenAlex/Crossref metadata acquisition, real-source rights catalogue, PWA/offline foundations, legal/commercial/onboarding/pilot templates.
- Connected tenant-scoped relational PostgreSQL export, object-storage-version export and Qdrant export plus checksum/restore-readiness drills.
- Seventeen tenant-owned tables, Alembic revision `20260726_0011`, v2.5 APIs, seven PlantUML diagrams, tests, validation and release documentation.

### Security

- Tenant integration and SSO configuration stores secret references rather than secret values.
- OIDC validates issuer, audience, time claims, signatures, state, nonce and redirect allowlists.
- Legal holds and retention block deletion; unsupported deletion adapters fail closed.
- Tenant backups run under forced RLS, export object/vector data using mandatory tenant boundaries, and produce SHA-256 manifests; whole-platform DR scripts remain operator controlled.
- PWA caching excludes authenticated API responses and confidential content.

### Status

- Cumulative source and unit validation pass. Live migrations, SMTP, SSO interoperability, enterprise sync, deletion, backup/restore, PWA, deployment, accessibility, performance, legal review and institutional pilot evidence remain pending.

## [2.4.0] - 2026-07-26

### Added

- Real durable handlers for in-app notification delivery, internal outbox publication, external-access expiry, reversible retention, analytics reports, audit exports, document ingestion, and teaching-output exports.
- Governed interval schedules materialised through a restricted PostgreSQL `SECURITY DEFINER` function.
- Notification-delivery evidence plus visible blocked status for unconfigured email, SMS, or webhook channels.
- Preview-first retention runs and per-resource retention evidence with no implicit hard deletion.
- Institution Administrator Platform operations view for jobs, schedules, retention and delivery evidence inside the unified workspace.
- Three tenant-owned tables, Alembic revision `20260726_0010`, five permissions, six PlantUML diagrams, runtime validation guidance, tests, and v2.4 documentation.

### Security

- The worker remains non-superuser and without `BYPASSRLS`.
- Scheduled jobs are idempotent and tenant owned.
- Retention supports only reversible archive or expiry actions; unsupported actions are recorded as skipped.
- Backup and restore-drill jobs continue to fail honestly until approved owner-machine destinations are configured.
- Institution Administrator and Head of Department responsibilities remain independent.

### Status

- Cumulative static and unit validation pass. Live migration, schedule dispatch, worker execution, MinIO, Qdrant, Ollama, browser, accessibility and backup/restore validation remain owner-machine pending.


## [2.3.0] - 2026-07-26

### Added

- Durable tenant-scoped background jobs, attempts, schedules, dead letters, backup runs, and restore-drill evidence.
- Restricted `lsa_worker` database role with no BYPASSRLS and security-definer claim/recovery functions.
- Bounded exponential retries, worker leases, idempotency keys, one-time dead-letter replay, and operational APIs.
- Security headers, streaming/request-size controls, Redis rate limiting, protected metrics, structured JSON logging, and recursive secret redaction.
- Optional ClamAV INSTREAM scanning for files and expanded ZIP members; production configuration requires fail-closed scanning.
- Dependency-aware PostgreSQL/Redis/MinIO/Qdrant/Ollama readiness checks.
- PostgreSQL/MinIO/Qdrant backup, checksum verification, guarded restore scripts, and restore-drill records.
- Non-root API, worker, and web Dockerfiles; hardened production Compose; Caddy gateway; Kubernetes base/overlays; Prometheus and alert rules.
- Deterministic 36-record synthetic academic corpus across 12 disciplines and a governed institution-onboarding JSON Schema/semantic validator.
- Six new database tables, Alembic revision `20260726_0009`, four operations permissions, eight PlantUML diagrams, CI gates, user guides, and v2.3 documentation.

### Security

- Institution Administrator and Head of Department remain independent; operational jobs and backup controls are Institution Administrator-only by default.
- Production startup rejects unsafe rate-limit, malware-scan, metrics, database-placeholder, trusted-host, and CORS configuration.
- The worker service role is restricted, tenant-scoped after claim, and does not receive BYPASSRLS.
- Disabled malware scanning reports `disabled` rather than pretending that content was scanned.

### Status

- Cumulative static and unit validation pass. Live migration, worker jobs, ClamAV, backups/restores, container deployment, browser, accessibility, performance, and pilot validation remain pending.

## [2.2.0] - 2026-07-26

### Added

- Role-scoped teaching and operational analytics for personal, organisational-unit and institution contexts.
- Immutable analytics snapshots, report definitions, report runs and actionable insight alerts.
- Multi-provider AI usage policies with allow/deny controls, local-only privacy classes, source-required tasks and monthly usage limits.
- User-specific daily AI usage ledger integrated into the conversation execution path.
- Institution Administrator Audit Centre for tenant audit/security search and checksum-protected JSON/CSV exports.
- Versioned non-secret commercial platform settings with secret-reference-only enforcement.
- Unified Insights, Reports, Audit centre and Platform settings panels with role-aware navigation.
- Eight tenant-owned tables, Alembic revision `20260726_0008`, 16 new scoped permissions, seven PlantUML diagrams and v2.2 documentation.

### Security

- Personal analytics are user-scoped; department and institution analytics fail closed when the active role lacks authority.
- Audit Centre and settings management remain Institution Administrator-only.
- Raw API keys, passwords, tokens and private keys are rejected from platform settings.
- Provider allow/deny and local-only policy is enforced before model routing.

### Status

- Cumulative unit and static release validation pass. Live migration, RLS, provider usage, reports, browser preview, accessibility and performance remain owner-machine validation pending.

## [2.1.0] - 2026-07-25

### Added

- Commercial unified navigation for conversation, Search, Library, Files, Saved outputs, Notifications and contextual role actions.
- Server-authorised search across owned conversations, generated outputs, accessible document versions and assigned review tasks.
- Library and Files views with immutable version, visibility, indexing and access labels plus attach-to-conversation actions.
- Personal Saved outputs tied to exact immutable output versions.
- Recipient-specific notifications, unread badges, read/unread controls and synthetic validation fixtures.
- Responsive commercial resource views, keyboard search, loading/empty/error states and light/dark appearance.
- Two tenant-owned tables, Alembic revision `20260725_0007`, governance-schema RLS coverage, three permissions, seven PlantUML diagrams and v2.1 documentation.

### Status

- 90 unit tests and cumulative static validators pass. Live migration, RLS, build, preview, accessibility and end-to-end behaviour remain owner-machine validation pending.

## [2.0.0] - 2026-07-25

### Added

- Consolidated owner-machine validation orchestration for static, runtime and live-preview stages.
- Secret-safety checks, exact Ollama model verification, PostgreSQL/Redis/MinIO/Qdrant/API/web probes and optional synthetic cloud-provider probes.
- Playwright role previews for Institution Administrator, Head of Department, Lecturer, Internal Moderator and External Reviewer at desktop, tablet and mobile breakpoints.
- Redacted timestamped evidence, machine-readable summary, human-readable report, failure triage, rollback guidance and Claude handover gate.
- Validation profile JSON Schema, GitHub static-validation workflow, five PlantUML diagrams and v2.0 governance documentation.

### Status

- The validation harness is statically validated. Cumulative runtime behaviour remains owner-machine pending until the full report passes.

## [1.9.0] - 2026-07-25

- Added teaching plans, session monitoring, module readiness, workload, academic calendar, handovers, and departmental operations dashboards.
- Added 11 tenant-owned tables, 12 scoped permissions, 7 UML diagrams, unit tests, and validation guidance.

## [1.8.0] - 2026-07-25

### Added

- Assignment-specific internal moderation, external moderation, external review and quality-review cycles.
- Exact-version sealed review packs, deterministic manifest hashes and review-pack items.
- Reviewer task acceptance, start, findings, immutable submissions and recommendations.
- Formal academic decisions separated from reviewer recommendations.
- Blocking findings, lecturer/coordinator responses, correction rounds and resubmission as new immutable output versions.
- Departmental review oversight counts for active, pending, overdue and blocking work.
- Contextual review-cycle, review-task and review-dashboard controls in the unified work area.
- Eight review-domain tables, extended assigned-review tasks, Alembic revision `20260725_0005`, seven PlantUML diagrams and cumulative validation.

### Security

- Review permission is insufficient without exact task assignment.
- External access is rechecked for grant state, time window, allowed action and exact resource scope on every review operation.
- External reviewers and moderators cannot formally approve or release outputs.
- Institution Administrators do not receive academic review-decision authority.
- Grant revocation and due-grant expiry are auditable and fail closed.

### Validation

- Python compilation, TypeScript/TSX syntax validation, **68 unit tests**, 77 SQLAlchemy tables, 81 FastAPI routes and 70 PlantUML sources passed static validation.
- PostgreSQL migrations/RLS, live grant expiry/revocation, browser preview, responsive accessibility and end-to-end review cycles remain owner-machine validation pending.

## [Unreleased]


## [1.7.0] - 2026-07-25

### Added

- Authorised lecturer module context with immutable per-request snapshots.
- Production output blueprints and inline generated-output lifecycle.
- Append-only manual edits, restore-as-new-version and workflow history.
- Assessment role gates, persisted safety reviews and student-copy controls.
- Markdown, HTML, DOCX, PDF, PPTX and XLSX export generation with object-storage records.
- Five tenant-owned tables and Alembic revision `20260725_0004`.
- Provider-neutral artifact JSON Schemas and seven v1.7 PlantUML diagrams.

### Security

- Academic approval remains separate from institution administration.
- Review-only roles cannot create unrelated assessments.
- Student exports fail closed on personal-data or unresolved safety blockers and remove answer sections.
- Every output, version, workflow action and export is re-authorised by tenant, active role and organisational scope.

### Validation

- Packaging/static validation and **58 unit tests** completed; live database, object storage, providers, web build, browser, accessibility and end-to-end role workflows remain owner-machine pending.



## [1.6.0] - 2026-07-25

### Added

- Contextual bulk-upload and message-attachment experience inside the unified work area.
- Safe ZIP expansion, common academic file parsers, transcript-required media handling, deterministic chunking, Ollama embeddings and Qdrant indexing.
- Five tenant-owned ingestion/retrieval tables and Alembic revision `20260725_0003`.
- Defence-in-depth document-version access checks, institutional retrieval traces, institutional source cards and prompt excerpts.
- Permission-enforced document lifecycle transitions (`working`, review, approval, publication, supersession and archive) with append-only transition evidence.
- Owner and organisational-scope checks inside the versioning service, not only at the route layer.
- Six v1.6 PlantUML diagrams, ADR-010, acceptance criteria, implementation evidence and validation scripts.

### Security

- ZIP path traversal, symbolic links, encryption, nested archives and expansion abuse are rejected.
- Every Qdrant search is tenant-filtered and every returned version is re-authorised in PostgreSQL.
- Unsupported media never receives invented extracted text.

### Validation

- Static validation and **40 unit tests** completed in the packaging environment; owner-machine migration, MinIO, Ollama, Qdrant, web build, live preview, accessibility and end-to-end tests remain pending.


## [1.5.0] - 2026-07-24

### Added

- Functional unified conversation API and persistence for all authorised lecturer-support requests.
- Explainable teaching-task, privacy, source-need, institutional-context, and human-review classification.
- Provider-native adapters for OpenAI Responses, Anthropic Messages, Gemini generateContent, DeepSeek chat completions, Ollama chat, and a development-only deterministic mock.
- Privacy-aware routing and fallback with optional Ollama-only handling for confidential and restricted-assessment content.
- Generic-by-default prompt behaviour with optional institutional context.
- Crossref scholarly metadata discovery, numbered source packs, inline source cards, and retrieval provenance.
- Citation integrity guard that removes unknown source markers, URLs, and DOIs instead of accepting fabricated references.
- Inline generated-output versions, provider attempts, source retrievals, citations, verification records, audit events, and conversation history.
- Commercial unified web-work-area foundation with recent conversations, loading and recovery states, inline outputs, source cards, human-review notices, mobile navigation, and contextual role actions.
- Six v1.5 PlantUML diagrams, ADR-009, API/AI/UX/requirements/testing/operations documentation, and cumulative validation scripts.

### Security

- Provider-status responses expose configuration state and model names, never API keys.
- Production configuration rejects the development AI mock.
- Provider errors return a safe 503 response without raw provider payloads or credentials.
- Restricted requests can fail closed when the approved local provider is unavailable.
- OpenAI adapter requests use `store=false`; all real provider keys remain local environment secrets.

### Validation

- 30 unit tests passed, Python compilation passed, 59-table metadata loaded, 39 FastAPI routes loaded, 23 JSON files parsed, 50 PlantUML sources structurally checked, and TypeScript/TSX syntax validation passed.
- Live database, provider, Crossref, Ollama, production web build, browser preview, accessibility, and end-to-end validation remain owner-machine pending.


## [1.4.0] - 2026-07-24

### Added

- Argon2id password credentials, institution-aware login, active-role selection, fixed-algorithm JWT access tokens, rotating opaque refresh sessions, per-request active-session validation, lockout, logout, and invitation acceptance.
- Restricted `lsa_auth` database role and six identity/position/session tables, bringing SQLAlchemy metadata to 59 tables.
- Tenant user invitation, membership lifecycle, scoped role assignment/revocation, institution position labels, and position assignments.
- Configurable organisational unit types, hierarchy creation/update/move, terminology, and tenant settings.
- HOD lecturer, coordinator, and moderator assignment APIs plus department teaching overview.
- Responsive Next.js 16.2.11 unified shell, role action rail, HTTP-only-cookie BFF, sign-in, and invitation acceptance.
- Six v1.4 PlantUML diagrams, ADR-008, security/API/UX/testing documentation, and validation/startup scripts.

### Security

- Authorisation is constrained to the role assignment selected for the signed session.
- `lsa_app` cannot read password credentials; `lsa_auth` remains RLS-constrained and narrowly granted.
- Development header authentication is disabled by default and production rejects template JWT secrets or exposed invitation tokens.
- Browser JavaScript does not receive refresh tokens or provider API keys.

### Validation

- 20 unit tests passed, Python compilation passed, 59-table metadata loaded, 33 FastAPI routes loaded, and TypeScript/TSX syntax validation passed.
- Owner-machine database, API, web build, browser preview, and integration validation remain pending.


## [1.3.0] - 2026-07-24

### Added

- Physical PostgreSQL schema with 53 SQLAlchemy tables across 11 domain schemas.
- Alembic baseline migration, tenant foreign keys, forced row-level security and tenant-filtered identity views.
- Configurable institutional hierarchy, academic assignments, immutable content versions, sources/citations, unified conversations, external access, workflows and audit/outbox records.
- FastAPI foundation for documents, contextual bulk uploads, lecturer assignments and external access.
- MinIO/S3 object-versioning, Qdrant tenant-filter and Redis temporary-state integrations.
- Docker Compose local data stack and Windows PowerShell database lifecycle scripts.
- Independent role/permission seed catalogue and two synthetic isolated demonstration tenants.
- Controlled dataset acquisition approval schema and quarantine downloader.
- Six new PlantUML diagrams, ADR-007, implementation documentation and tests.

### Security

- Real `.env` files and runtime secrets remain excluded.
- Added safe project archive generation with local secret scanning.
- Application role is non-superuser and cannot bypass PostgreSQL RLS.


### Added

### Multi-Provider AI and Local Model Pack

- Expanded the provider-neutral gateway to OpenAI, Anthropic Claude, Google Gemini, DeepSeek API and Ollama.
- Added capability/policy routing, privacy-safe fallback, provider data-handling and local-model governance documentation.
- Added provider, model and Ollama profile registries with three JSON Schemas.
- Added Windows PowerShell scripts to install Ollama, pull minimal/standard/advanced model profiles, write a local inventory and test configuration.
- Added two PlantUML diagrams and ADR-006.
- Model binaries are intentionally not bundled; they are pulled on the target Windows host.


### Data Foundation and Model Readiness Pack

- Added the complete data strategy, requirements catalogue, source register, acquisition plan, model-adaptation strategy, database architecture, governance, classification, licensing, privacy, institutional onboarding, bulk-upload, immutable versioning, source-verification, evaluation and red-team specifications.
- Added eight Draft 2020-12 JSON Schemas with safe example manifests and evaluation fixtures.
- Added six editable PlantUML data-foundation diagrams and an automated validation script.
- No third-party or institutional dataset content was downloaded into the repository; the acquisition register contains planning metadata and rights decisions only.

- Professional repository scaffold.
- Master blueprint, requirements, role separation, bulk-upload scenarios, immutable versioning, PlantUML diagrams, UX, AI, security, testing, operations, and research documentation.
