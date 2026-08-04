# Lecturer Support Agent v2.6.0 — deployment-ready source release

## Release status

**Source package:** GO  
**Managed-service deployment:** owner action required  
**Production acceptance:** requires staging parity, institutional approval, legal/privacy approval, security acceptance and production verification

## Included

- Complete cumulative Lecturer Support Agent implementation through v2.5.
- All eight approved user roles and one unified ChatGPT-style work area.
- PostgreSQL/Alembic multi-tenant data model with row-level security.
- Immutable file and teaching-output versioning, moderation, external review, departmental operations, analytics and governance.
- OpenAI, Claude, Gemini, DeepSeek and Ollama provider-neutral AI gateway.
- Hosted Gemini/OpenAI embeddings for managed deployment.
- Vercel frontend configuration.
- Render staging and production Blueprints for API, worker, temporary Redis state and ClamAV.
- Neon migration/role bootstrap and pre-deploy validation.
- Private versioned S3-compatible storage and Qdrant migration contracts.
- Controlled SSO/invitation/access-request identity model.
- Approved local-data export/import, object-version migration, Qdrant migration and fail-closed parity verification.
- GitHub CI, CodeQL, dependency review, secret scanning and container builds.
- Safe release packaging and deployment runbooks.

## Validation summary

- 153 unit tests passed in the clean packaging environment.
- Five Windows-specific event-loop tests were correctly skipped on Linux.
- All cumulative release validators through v2.6 passed.
- TypeScript/TSX structural syntax validation passed.
- JSON and YAML parsing passed.
- High-confidence repository secret scan passed.
- Prior owner-machine baseline: all eight role previews, 151 unit tests and 94 integration tests.

## Deliberate exclusions

The archive excludes real environment files, API keys, passwords, private keys, sessions, token material, password hashes, local databases, runtime evidence, model binaries, caches, local Redis state and unapproved institutional data.

## Owner deployment sequence

1. Read `PUSH_AND_DEPLOY.md` and `DEPLOYMENT_QUICKSTART.md`.
2. Push to a private GitHub repository.
3. Allow GitHub CI/security gates to pass.
4. Create separate staging services and populate protected secrets.
5. Deploy Render/Neon/S3/Qdrant/SMTP and Vercel.
6. Migrate approved local PostgreSQL, object and vector data using the parity runbook.
7. Recreate secure staging credentials for all eight test roles.
8. Verify all online workflows and local-to-staging parity.
9. Obtain required approvals.
10. Promote the same validated release to production with separate credentials and approved production data.

## Mandatory rule

A deployment is not complete until the validated application version, migration head, roles, permissions, approved data, object checksums, vector metadata, authentication and all eight role workflows are proven in the deployed environment. Redis starts clean.
