# Phase 14 — v2.5 Completion Gap Closure Implementation Report

## Purpose

v2.5 closes the implementation gaps that can be completed before live institutional credentials, production infrastructure, legal approval, and owner-machine evidence are available. It preserves the one-work-area product model and the independence of the Institution Administrator and Head of Department.

## Implemented scope

### Account-security completion

- Privacy-preserving password-reset request and confirmation.
- Email-verification challenges.
- TOTP multi-factor authentication with encrypted device secrets and single-use recovery codes.
- Immediate session revocation after password reset.
- OIDC Authorization Code with PKCE, state, nonce, discovery, JWKS signature verification, issuer/audience validation, and explicit account-linking policy.
- Federated-identity records and one-time SSO handoff tokens.

### Enterprise integration fabric

- Tenant-owned integration connections using secret references rather than secret values.
- Canvas, Moodle, OneRoster CSV, OneRoster REST, and governed generic REST adapters.
- Staged synchronisation runs, external-record mappings, cursors, idempotency and audit evidence.
- No silent write into canonical academic records; imported data remains staged until an authorised mapping/approval step.

### Communication and delivery

- SMTP delivery abstraction and durable outbound-message records with encrypted message bodies at rest.
- Invitation, password-reset, email-verification, review and operational message contracts.
- Unsupported channels remain visibly blocked rather than marked as delivered.

### Privacy and deletion

- Legal holds, deletion requests, component actions, second approval and durable execution.
- Exact MinIO/S3 object-version deletion and Qdrant document-version removal.
- Audit tombstones remain while physically deleted content is removed.
- Unsupported resource deletion remains pending a reviewed adapter.

### Backup and recovery execution

- Tenant-scoped relational PostgreSQL exports generated through the RLS-constrained worker session; whole-platform disaster-recovery dumps remain operator-controlled.
- Tenant-prefix object-storage version export.
- Tenant-filtered Qdrant point export.
- SHA-256 backup manifests and partial-failure evidence.
- Non-destructive restore drills verify every manifest item and tenant relational export; legacy/platform PostgreSQL archives are catalogue-checked when present.
- A full isolated restore can be delegated to an explicitly configured, institution-approved executable.

### Real-data preparation

- Governed data-source catalogue with licence, commercial-use, training-use, retrieval-use and review status.
- Metadata-only OpenAlex and Crossref acquisition into versioned object storage.
- Manual item/title-level rights gates for OER repositories whose licences vary.
- Evaluation data remains separate from retrieval and adaptation data.
- No third-party full text is bundled in the release.

### Evaluation and feedback

- User output feedback, source feedback and issue reporting.
- Evaluation campaigns, role/discipline cohorts and immutable responses.
- Pilot instrument covering usefulness, pedagogical quality, source trust, time saved, usability and safety.

### Commercial release preparation

- Installable PWA metadata, service worker, offline fallback and reconnect-safe navigation foundations.
- Institution onboarding, support, pilot, legal and tenant-exit templates.
- Production settings reject unsafe secret, rate-limit, malware-scan, host, CORS and backup-encryption configuration.

## Explicit boundaries

- Institution-specific SSO credentials, integration credentials and mail credentials are not included.
- SAML is represented as a future adapter contract; OIDC is the implemented federated-login protocol.
- Integration synchronisation stages external records but does not make destructive canonical changes automatically.
- Claim verification checks retrieval provenance and citation coverage; it does not falsely claim semantic entailment.
- Real OER full text is not bundled until item-level rights and intended-use approval are recorded.
- Legal templates require professional review in the deployment jurisdiction.
- Production deployment and full restore evidence remain owner-machine/staging validation requirements.

## Status

**Implemented — statically validated — owner-machine and institutional acceptance validation pending.**
