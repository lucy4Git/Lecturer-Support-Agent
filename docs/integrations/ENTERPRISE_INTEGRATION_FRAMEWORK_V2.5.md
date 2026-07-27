# Enterprise Integration Framework v2.5

## Purpose

The Lecturer Support Agent remains usable as a standalone platform while providing governed adapters for institutional systems. Integrations are tenant-specific, optional, secret-reference based, auditable, and staged before they can modify canonical academic records.

## Implemented adapters

| Adapter | Protocol | Implemented scope | Safety boundary |
|---|---|---|---|
| Canvas | Official HTTPS JSON API | Courses, users and enrolments | Bearer token is read from an environment-variable reference; imported records are staged |
| Moodle | Official external web-service REST framework | Site test, courses and users | Token remains outside the database; responses are staged |
| OneRoster 1.2 CSV | Institution-provided CSV package | Organisations, users, courses, classes and enrolments | File content is parsed and staged; mapping is reviewed before canonical write |
| Generic REST | Contract placeholder | Future institution-specific systems | Must implement the shared adapter interface and pass security review |

## Synchronisation workflow

1. Institution Administrator creates a connection using a secret reference, never a raw secret.
2. The adapter tests connectivity and records non-sensitive evidence.
3. A durable `integrations.sync` job is queued with an idempotency key.
4. Source records are retrieved and stored as staging evidence.
5. External identifiers are mapped to internal records through `governance.external_record_mappings`.
6. Conflicts remain `needs_review`; the worker does not silently replace institutional records.
7. Accepted mappings can later be applied by an institution-specific import policy.
8. Every operation is tenant-scoped and audited.

## SSO foundation

OpenID Connect Authorization Code with PKCE is implemented with:

- discovery-document issuer validation;
- allowlisted redirect URIs;
- random state and nonce challenges;
- short-lived, hashed one-time challenges;
- code exchange through a secret-reference environment variable;
- JWKS signature verification;
- issuer, audience, expiry and nonce validation;
- verified-email linking only when the tenant explicitly enables it;
- existing active membership and role requirements;
- a second one-time handoff before a normal role-scoped application session is issued.

SAML is retained as a configuration type but does not claim a completed runtime adapter. A production SAML implementation must validate signed metadata, assertions, audience, destination, replay and certificate rollover.

## Data mapping rules

- External records never become authoritative solely because an API returned them.
- The staging record preserves source payload, timestamp, checksum and connection.
- Institution-specific mapping rules must be versioned.
- Deactivation and deletion require explicit policy; absence in a source feed is not enough to delete a user or module.
- Cross-tenant mappings are prohibited.

## Runtime validation pending

Live Canvas, Moodle, OIDC and OneRoster institution packages require owner-machine or staging validation with approved test credentials. No real credentials are included in the repository.
