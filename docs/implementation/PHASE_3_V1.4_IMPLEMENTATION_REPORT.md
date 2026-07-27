# Phase 3 — v1.4 Identity, Administration, and Head of Department Foundation

**Checkpoint status:** Implemented; owner-machine runtime validation pending  
**Baseline:** Lecturer Support Agent v1.3  
**Release:** v1.4.0  
**Date:** 24 July 2026

## Purpose

v1.4 converts the approved identity, institutional administration, and departmental requirements into executable backend and web-client foundations. It does not implement AI generation; that remains the v1.5 checkpoint. This separation prevents an attractive interface from hiding unresolved authorisation or tenant-boundary defects.

## Implemented capabilities

### Production-oriented authentication

- Argon2id local password hashes with a configurable password policy.
- Signed, short-lived JWT access tokens with fixed algorithm configuration.
- Opaque, hashed, rotating refresh tokens.
- Institution and active-role selection at sign-in.
- Account lockout after repeated failed attempts.
- Tenant-scoped authentication sessions with revocation and rotation history.
- Database-backed active-session validation on every authenticated API request, so logout, revocation, and token rotation take effect immediately.
- Invitation acceptance without using invitation tokens as passwords.
- Separate restricted `lsa_auth` and normal application `lsa_app` database roles.
- Development header authentication disabled by default.

### Independent active roles

A user may hold multiple role assignments, but a session activates only one. Authorisation queries are constrained by both the role code and selected role-assignment identifier in the signed token. A user signed in as Head of Department cannot silently receive Institution Administrator permissions from another assignment.

### Institution Administrator operations

- List authorised tenant users through a security-barrier tenant view.
- Invite users with one or more independently scoped roles.
- Activate, suspend, or deactivate institutional memberships.
- Assign and revoke roles and access scopes.
- Create institution-specific position labels and assign them to members.
- Configure organisational unit types, units, terminology, and non-secret tenant settings.
- Preserve audit and outbox evidence for every administrative change.

### Configurable HEI structure

- Create arbitrary unit types such as campus, college, faculty, school, department, centre, or custom structures.
- Create, update, deactivate, and move organisational units.
- Maintain closure-table ancestry and materialised paths.
- Prevent cycles when moving a hierarchy branch.
- Keep institutional terminology independent from the codebase.

### Head of Department operations

- Assign and reassign lecturers to module offerings while retaining previous assignments.
- Assign module or programme coordinators.
- Assign internal or external moderators to approved academic targets.
- End a lecturer assignment with an effective date and reason.
- Review a department teaching overview containing offerings, lecturer allocations, unassigned offerings, moderation, coordination, and workload totals.
- Apply department scope through the organisational-unit closure table.

### Unified web shell

- One responsive ChatGPT-style application shell.
- Contextual role actions appear in a right-side panel rather than a separate administrative application.
- Next.js backend-for-frontend route handlers keep access and refresh tokens in HTTP-only cookies.
- Invitation, institution-structure, course-assignment, and department-overview forms call secured APIs.
- The AI composer is visibly present but does not simulate successful generation before v1.5.

## Database changes

v1.4 adds six tables, bringing the SQLAlchemy metadata total to 59:

1. `iam.password_credentials`
2. `iam.position_definitions`
3. `iam.membership_positions`
4. `iam.user_invitations`
5. `iam.invitation_role_grants`
6. `iam.authentication_sessions`

The migration also creates the restricted authentication database role, extends RLS policies to that role, and removes application-role access to password credentials.

## Security decisions

- Password credentials are global to the person account because one person may belong to multiple institutions. Membership, role, session, invitation, and position records remain tenant-owned.
- Password hashes are never returned by an API or exposed through a tenant view.
- API keys remain external environment secrets and are unrelated to user login credentials.
- Refresh tokens are stored only as SHA-256 hashes.
- The browser receives neither cloud-provider API keys nor the refresh-token value.
- Production settings reject development header authentication, exposed invitation tokens, or template JWT secrets.
- User-facing role labels are not permissions; permissions are granted only by role assignments and access scopes.

## Validation completed in this environment

- Python syntax compilation: passed.
- SQLAlchemy metadata loading: 59 tables.
- FastAPI route loading: 33 routes.
- Unit tests: 20 passed.
- TypeScript/TSX syntax transpilation: passed.
- JSON role catalogue parsing: passed.
- Secret-template review: real credentials absent.

## Runtime validation deliberately deferred

The following remain `IMPLEMENTED — OWNER-MACHINE VALIDATION PENDING`:

- PostgreSQL migrations and `lsa_auth` grants.
- Live RLS checks for both application and authentication roles.
- Argon2 login against the seeded database.
- JWT login, refresh rotation, logout, and invitation acceptance end to end.
- Next.js package installation, full type checking, build, and browser preview.
- Live responsive and accessibility testing.
- Docker, Redis, MinIO, Qdrant, and Ollama integration regression.

Follow `docs/operations/V1.4_OWNER_MACHINE_VALIDATION.md` before Claude begins its audit or implementation work.
