# ADR-011 — Inline Output Lifecycle and Assessment Safety

- **Status:** Accepted
- **Date:** 2026-07-25

## Context

Lecturer-support outputs need editing, review, approval, release and export, but the product requirement prohibits a separate artifact workspace. High-stakes assessments also require stronger controls than ordinary chat responses.

## Decision

Generated outputs remain first-class versioned records linked to conversation messages and rendered inline. Each edit or restore appends an immutable output version. A separate lifecycle record controls academic state. Assessment-safety results are persisted per version. Module context is snapshotted per AI request. Exports are auditable records referencing the exact output version.

Academic approval permissions remain independent from institution administration. Student-facing copies are generated only from an authorised lifecycle state and remove confidential answer sections.

## Consequences

- Conversation history remains the primary user experience.
- Reproducibility and auditability improve.
- More database records and state transitions must be maintained.
- Automated safety remains advisory/guarding and never replaces academic review.
- Live owner-machine and role-based browser validation is mandatory before release.
