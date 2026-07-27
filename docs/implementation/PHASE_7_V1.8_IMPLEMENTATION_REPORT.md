# Phase 7 — v1.8 Moderation and External Review Implementation

## Purpose

v1.7 made teaching outputs editable, versioned, safety-checked, reviewable and exportable inside the unified conversation. v1.8 implements the formal review layer that sits between a lecturer's draft and an authorised academic decision.

The implementation deliberately separates four authorities:

1. **The lecturer or output owner** creates and corrects the material.
2. **The assigned moderator or reviewer** examines one exact version and submits evidence-based findings and a recommendation.
3. **The Head of Department, Module Coordinator or Programme Coordinator** records the authorised academic decision within scope.
4. **The Institution Administrator** manages the tenant but receives no automatic academic review-decision authority.

## Implemented capabilities

- internal moderation, external moderation, external review and quality-review cycles;
- exact-version, sealed review packs with deterministic SHA-256 manifests;
- one or more assignment-specific reviewer tasks per round;
- task acceptance, start, findings and immutable reviewer submissions;
- severity, criterion, evidence locator, recommendation and blocking status for findings;
- lecturer/coordinator responses and correction evidence;
- formal decisions: approved, approved with conditions, changes required or rejected;
- repeated correction and resubmission rounds without deleting previous evidence;
- temporary external access checks on every external read and write action;
- grant revocation and due-grant expiry processing;
- departmental review dashboard counts within authorised organisational scope;
- inline review controls in the existing work area, without a separate moderation portal.

## Database changes

Eight tenant-owned tables were added:

- `review.review_cycles`
- `review.review_packs`
- `review.review_pack_items`
- `review.review_findings`
- `review.review_finding_responses`
- `review.review_submissions`
- `review.review_decisions`
- `review.review_correction_rounds`

`review.assigned_review_tasks` was extended with cycle, pack, role, review kind, round, acceptance, start, submission and metadata fields.

## Security design

A broad role permission is never enough for a moderator. The service also requires that the current user is the exact task assignee. External users additionally require an active, unexpired, non-revoked grant whose action and resource boundary match the task, cycle, output and output version.

Reviewer recommendations are advisory evidence. They do not directly release the output. Academic approval remains a separate permission and action.

## Runtime status

The source, migration, static tests and validation contracts are implemented. PostgreSQL migration execution, row-level-security behaviour, live invitation/access expiry, browser workflows and end-to-end moderation remain **owner-machine validation pending**.
