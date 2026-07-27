# ADR-016 — Scoped Analytics, AI Usage Governance and Audit Centre

**Status:** Accepted for v2.2; owner-machine validation pending  
**Date:** 2026-07-26

## Context

The platform needs useful teaching and operational insight without exposing another institution's, department's or user's activity. It also requires commercial control over multi-provider AI use, auditable settings and an institutional Audit Centre while preserving independent academic and administrative roles.

## Decision

1. Analytics scope is derived server-side from the active role and authorisation scope.
2. Personal roles receive user-scoped analytics; department roles receive authorised organisational-unit analytics; institution scope is reserved for Institution Administrators.
3. Analytics snapshots and report runs are immutable and checksum-protected.
4. Provider and usage policy is evaluated before model routing.
5. Confidential privacy classes may be forced to approved local Ollama execution and fail closed when unavailable.
6. Raw secrets are never stored as platform settings; references only are permitted.
7. Audit Centre and commercial-settings management are Institution Administrator capabilities and are not inherited by Heads of Department.
8. Insights, Reports, Audit Centre and Settings remain views in the unified application shell.

## Consequences

### Positive

- Tenant and scope controls are explicit and testable.
- AI provider governance is independent of user-facing model choice.
- Administrative audit functions do not contaminate academic roles.
- Reports and settings retain traceable history.
- The UX remains a single commercial application.

### Trade-offs

- Analytics queries may require optimisation and materialised snapshots at scale.
- Live token and cost figures depend on provider metadata quality.
- Strict local-only policy can reduce availability.
- Full proof requires real RLS, provider and browser validation.

## Rejected alternatives

- Client-selected analytics scope: rejected because it permits privilege escalation.
- One analytics role for every user: rejected because it would expose excessive data.
- Storing API keys in settings: rejected because masking does not make an uploaded secret safe.
- Giving Head of Department full Audit Centre access: rejected because the HOD and Institution Administrator are independent roles.
- A separate analytics application: rejected because the approved product uses one unified work area.
