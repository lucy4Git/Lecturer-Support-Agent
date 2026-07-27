# Moderation and Review Service Boundary

The v1.8 moderation and external-review capability is currently implemented inside the FastAPI application as a cohesive domain service while preserving this directory as the future independently deployable service boundary.

## Responsibilities

- create internal moderation, external moderation and external review cycles;
- seal exact-version review packs with deterministic SHA-256 manifests;
- assign one or more reviewers to a specific task and round;
- enforce task-assignee checks in addition to role permissions;
- enforce active, unexpired and non-revoked external-access grants;
- record findings, evidence locators, responses and immutable submissions;
- separate reviewer recommendations from formal academic decisions;
- preserve correction and resubmission rounds without rewriting prior evidence;
- expose authorised departmental review-oversight data;
- emit complete audit evidence for review actions.

## Current implementation

- Models: `services/database/models/reviews.py`
- External-task model: `services/database/models/external_access.py`
- Service: `services/api/app/services/moderation_review.py`
- Routes: `services/api/app/routes/reviews.py`
- Schemas: `services/api/app/schemas/reviews.py`
- Migration: `services/database/migrations/versions/20260725_0005_v18_moderation_external_review.py`
- Unit tests: `tests/unit/test_v18_moderation_review.py`

## Governance boundary

The Institution Administrator remains independent from academic review authority. Formal decisions are restricted to authorised Heads of Department, Module Coordinators or Programme Coordinators within scope. Internal moderators, external moderators and external reviewers may act only on tasks assigned to them. External users additionally require a matching temporary grant for the exact resource boundary.

## Runtime status

The source implementation and infrastructure-independent tests are complete. Live PostgreSQL migrations, row-level-security enforcement, grant expiry, browser workflows and end-to-end review execution remain **owner-machine validation pending**.

Implementation must continue to follow `PROJECT_CONSTITUTION.md`, the role-permission matrix, ADR-012 and the v1.8 security specification.
