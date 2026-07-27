# ADR-008 — Active-Role Sessions and Web Backend-for-Frontend

## Status

Accepted for v1.4; runtime validation pending.

## Decision

Each authenticated session activates exactly one role assignment. The JWT carries the tenant, membership, selected role, selected role-assignment, and session identifiers. Permission checks filter by that assignment.

The web application uses Next.js route handlers as a backend-for-frontend. Access and refresh tokens are stored in HTTP-only SameSite cookies and are not exposed to browser JavaScript.

## Rationale

- One person can legitimately be both a lecturer and a Head of Department or Administrator.
- Automatically combining permissions would weaken role independence and audit interpretation.
- A selected active role makes every action attributable to a clear authority context.
- HTTP-only cookies reduce browser-script access to tokens.
- Backend permission and RLS checks remain authoritative even if UI metadata is altered.

## Consequences

- Users with several roles select a role at sign-in or explicitly switch through a future controlled session flow.
- A role switch creates or refreshes a new signed context rather than changing a browser label.
- The web BFF becomes a security boundary and must receive the same review as public API endpoints.
- CSRF, TLS, cookie-domain, and reverse-proxy configuration must be validated during deployment.
