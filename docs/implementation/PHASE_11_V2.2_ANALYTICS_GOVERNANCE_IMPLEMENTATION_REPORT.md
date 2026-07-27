# Phase 11 — v2.2 Analytics, Reporting and Governance Implementation Report

## Status

**IMPLEMENTED — STATICALLY VALIDATED — OWNER-MACHINE VALIDATION PENDING**

## Purpose

v2.2 adds a commercial operational-intelligence layer without changing the product's core interaction model. Teaching analytics, reports, AI governance, audit controls and platform settings remain views inside the unified Lecturer Support Agent application rather than becoming separate applications or AI workspaces.

## Implemented capabilities

### Scoped teaching insights

The analytics service produces tenant-filtered summaries for conversations, generated teaching outputs, authorised materials, teaching delivery, module readiness, moderation progress, workload and operational alerts. Scope is resolved server-side from the active role:

- lecturers and reviewers receive personal analytics;
- Heads of Department and coordinators receive authorised organisational-unit analytics;
- Institution Administrators may receive institution-wide analytics;
- unsupported scope requests fail closed.

Every generated overview can be persisted as an immutable analytics snapshot with the period, scope, data watermark and requesting user.

### Governed reporting

Authorised users may access report definitions and create immutable report runs. A report run retains the exact report type, period, scope, parameters, format, result payload and SHA-256 digest. Initial report families cover teaching operations, module readiness, moderation progress and AI usage governance.

### AI usage governance

Policies may restrict allowed providers, deny providers, force local-only processing for confidential content, require sources for designated task types and set monthly request, token or estimated-cost limits. The conversation engine evaluates policy before provider routing and records daily usage after execution.

API keys and other secret values are not stored in policy or platform-setting records.

### Audit Centre

The Audit Centre provides Institution Administrators with scoped search over audit and security events and creates checksum-protected JSON or CSV audit exports. Heads of Department and ordinary academic users do not inherit this institutional-administration capability.

### Configurable commercial settings

Institution Administrators can manage versioned, non-secret settings for appearance, terminology, analytics defaults and institution configuration. Secret-backed settings may store only an environment-variable or secret-manager reference.

### Unified commercial interface

The existing workspace adds role-aware **Insights**, **Reports**, **Audit centre** and **Platform settings** destinations. They are integrated into the same responsive application shell, while ordinary users still begin work from one conversation area.

## Data changes

Eight tenant-owned tables were introduced:

1. `governance.platform_settings`
2. `governance.ai_usage_policies`
3. `analytics.ai_usage_daily`
4. `analytics.analytics_snapshots`
5. `analytics.report_definitions`
6. `analytics.report_runs`
7. `analytics.insight_alerts`
8. `audit.audit_export_jobs`

The cumulative model now contains 98 SQLAlchemy tables across 12 PostgreSQL schemas, including the new `analytics` schema.

## Security decisions

- Analytics scope is derived from role and rechecked through the authorisation service.
- Personal analytics use `user_id`, not a role-wide aggregate.
- All analytics records are tenant-owned and covered by PostgreSQL row-level-security policy generation.
- Audit Centre and settings management remain Institution Administrator capabilities.
- AI provider policy is applied before routing; restricted data may fail closed when an approved local provider is unavailable.
- Secret-looking keys or values are rejected from persistent platform settings.
- Report and audit-export payloads receive deterministic SHA-256 digests.

## Static evidence

The v2.2 unit suite tests table registration, scope failure behaviour, policy enforcement, provider filtering, permission separation, migration/RLS coverage, secret protection and unified-interface integration.

## Runtime dependencies still pending

The following require owner-machine validation:

- Alembic migration against PostgreSQL;
- row-level-security behaviour under `lsa_app`;
- live analytics against seeded tenant data;
- AI daily-ledger writes during real Ollama and cloud-provider calls;
- report and audit export generation against the live database;
- Next.js production build and live role-based browser testing;
- responsive and accessibility validation;
- performance and concurrency baselines.

No production-readiness claim is made until the consolidated validation report records `validated_on_owner_machine`.
