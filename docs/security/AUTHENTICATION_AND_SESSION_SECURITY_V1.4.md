# Authentication and Session Security — v1.4

## Trust boundaries

1. The browser sends credentials only to the web backend-for-frontend or FastAPI over TLS.
2. The web backend stores access and refresh tokens as HTTP-only, SameSite=Strict cookies.
3. FastAPI validates access-token signature, issuer, audience, type, expiry, and required claims.
4. PostgreSQL verifies that the signed session ID is still active, unexpired, and bound to the same tenant, user, membership, and role assignment.
5. PostgreSQL separately checks the selected role assignment and permission at request time.
6. RLS applies the tenant context to every tenant-owned query.

## Token design

### Access token

Required claims:

- `sub`: user ID
- `tenant_id`
- `membership_id`
- `role_assignment_id`
- `role_code`
- `session_id`
- `jti`
- `iat`, `nbf`, `exp`
- `iss`, `aud`
- `typ=access`

The configured algorithm is fixed server-side. It is never selected from untrusted token headers. Every protected request also verifies the backing database session, so a revoked session cannot continue until access-token expiry.

### Refresh token

The refresh token is opaque and formatted only to permit fail-closed tenant and session lookup. Its random secret is not interpreted. PostgreSQL stores a SHA-256 hash, not the token. Every refresh revokes the old session and creates a linked replacement session.

## Password controls

- Argon2id hashing.
- Minimum 12 characters by default.
- Upper-case, lower-case, number, and special-character classes by default.
- Configurable Argon2 memory, iterations, and parallelism.
- Failed-attempt counter and time-limited lockout.
- Password hashes are inaccessible to `lsa_app` and omitted from all views.

## Invitation controls

- Random, time-limited token stored only as a hash.
- Tenant identifier enables RLS context before token lookup.
- Invitation roles and scopes are stored as grants and materialised only after acceptance.
- Existing passwords are never reset through invitation acceptance.
- Raw invitation links are returned only when explicitly enabled in non-production development.
- Production is expected to deliver links through a separately audited notification service.

## Active-role rule

A user may have several role assignments but each session activates one. Authorisation is constrained by:

- tenant ID;
- user ID;
- membership status;
- signed role code;
- signed role-assignment ID;
- assignment validity period and revocation status;
- permission code; and
- requested organisational scope.

This prevents additive privilege leakage between Institution Administrator and Head of Department roles.

## Remaining production work

- Integrate institutional SSO using OIDC or SAML through a verified identity provider.
- Add email delivery and single-use password-reset workflows.
- Add optional MFA/WebAuthn.
- Add device/session management UI.
- Add CSRF token enforcement for state-changing BFF routes if deployment requires cross-site cookie modes.
- Establish key rotation, signing-key identifiers, and production secret management.
