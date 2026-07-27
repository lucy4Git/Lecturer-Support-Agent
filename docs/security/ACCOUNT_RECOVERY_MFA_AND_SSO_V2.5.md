# Account Recovery, MFA and SSO Security v2.5

## Implemented controls

### Password recovery

- The request response does not disclose whether an account exists.
- Reset tokens are high-entropy, tenant-prefixed, single-use and stored only as SHA-256 hashes.
- Tokens expire according to configuration.
- A successful reset increments password version, records a security event and revokes active sessions.
- Email delivery is durable and provider-neutral. A disabled provider records `blocked`, not `sent`.

### Email verification

- Verification tokens are single-use and hashed.
- Confirmation updates the user profile with verification evidence rather than exposing a token.
- Email templates and delivery evidence are retained without storing provider credentials.

### TOTP MFA

- TOTP follows RFC 6238-compatible SHA-1 time-step calculation.
- Secrets are encrypted with a deployment key before database storage.
- Enrolment remains pending until the user proves possession.
- Recovery codes are generated once and stored only as password hashes.
- Login returns a clear MFA-required precondition without creating a session.
- Invalid MFA attempts create security evidence.

### OpenID Connect

- Authorization Code with PKCE is used.
- State, nonce, issuer, audience, signature and expiry are validated.
- Redirect URIs must be allowlisted in the tenant connection metadata.
- Federated identities are linked by provider subject.
- Linking by email is allowed only when the provider marks the email verified and the tenant explicitly enables verified-email linking.
- A federated identity still requires an active membership and role assignment.

## Secret handling

The database stores references such as `MICROSOFT_ENTRA_CLIENT_SECRET`, not the value. Real values remain in an ignored `.env` file for development or a production secret manager.

## Remaining environment-specific controls

Institutional SSO metadata, conditional-access policy, phishing-resistant passkeys, domain verification and provider-specific logout require tenant deployment configuration and live validation.

## Sensitive outbound-message storage

Password-reset, verification and invitation URLs must survive long enough for durable delivery, but raw tokens must not be readable in ordinary database rows. v2.5 therefore encrypts queued email bodies before storage and decrypts them only inside the delivery worker. Production requires a dedicated `MESSAGE_CONTENT_ENCRYPTION_KEY`; logs and audit records retain only identifiers, hashes and delivery status.
