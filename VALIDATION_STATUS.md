# Validation status — v2.6.0

## Completed in source package

- Owner-machine technical validation and eight-role live-preview validation from v2.5.
- 153 unit tests pass in the v2.6 source package; five Windows-only event-loop tests are correctly skipped outside Windows.
- Deployment descriptors, migration head, hosted embeddings, controlled onboarding, seed guards and migration/parity tooling are statically validated.
- No real `.env` file is included or inspected by the v2.6 packaging process.

## Required after push

- GitHub CI, CodeQL and container builds.
- Render Blueprint validation and staging deployment.
- Neon migration/role bootstrap.
- S3 versioning, Qdrant collection and SMTP delivery checks.
- Vercel production build and browser workflows.
- Local-to-staging parity manifest verification.
- All eight staging roles, authentication/onboarding, uploads, AI, review and export workflows.
- Production legal, privacy, institutional and infrastructure approval.


## Package acceptance

The source package is ready for a private GitHub push. It is not represented as already deployed. Managed-service deployment is accepted only after the staging parity runbook and all eight online role workflows pass.
