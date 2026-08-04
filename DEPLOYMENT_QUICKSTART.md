# Deployment Quickstart — Lecturer Support Agent v2.6.0

This repository is prepared for a private GitHub repository with:

- **Vercel** — Next.js frontend (`apps/web`)
- **Render** — FastAPI API, background worker, Redis-compatible Key Value, and ClamAV
- **Neon** — PostgreSQL with four least-privilege roles and row-level security
- **AWS S3** (recommended) — versioned object storage
- **Qdrant Cloud** — tenant-filtered vector retrieval
- **Resend SMTP or another SMTP provider** — invitations, verification, and password recovery
- **OpenAI, Claude, Gemini, DeepSeek, and/or a private Ollama service** — provider-neutral AI execution

No real `.env` file, API key, password, token, database backup, model binary, or unredacted runtime evidence belongs in Git.

## 1. Push to GitHub

1. Create a **private** GitHub repository.
2. Push this extracted source folder.
3. Enable branch protection, secret scanning, push protection, Dependabot, and CodeQL.
4. Require the `CI`, `CodeQL`, and `Deployment release gate` checks before merge.

```powershell
git init
git add .
git commit -m "release: Lecturer Support Agent v2.6.0 deployment-ready"
git branch -M main
git remote add origin <YOUR_PRIVATE_GITHUB_REPOSITORY>
git push -u origin main
```

## 2. Create managed services

Create separate **staging** and **production** resources. They must never share databases, storage buckets, Qdrant collections, Redis, credentials, or encryption keys.

### Neon

Create a PostgreSQL project/database and retain the **direct owner connection string** for `MIGRATION_DATABASE_URL`. Use SSL. Application URLs use the runtime roles created by the pre-deploy script:

```text
DATABASE_URL=postgresql+psycopg://lsa_app:<URL_ENCODED_PASSWORD>@<POOLED_HOST>/<DATABASE>?sslmode=require
AUTH_DATABASE_URL=postgresql+psycopg://lsa_auth:<URL_ENCODED_PASSWORD>@<POOLED_HOST>/<DATABASE>?sslmode=require
WORKER_DATABASE_URL=postgresql+psycopg://lsa_worker:<URL_ENCODED_PASSWORD>@<POOLED_HOST>/<DATABASE>?sslmode=require
MIGRATION_DATABASE_URL=postgresql+psycopg://<NEON_OWNER>:<PASSWORD>@<DIRECT_HOST>/<DATABASE>?sslmode=require
```

Use unique, randomly generated passwords in:

```text
POSTGRES_APP_PASSWORD
POSTGRES_AUTH_PASSWORD
POSTGRES_WORKER_PASSWORD
```

The pre-deploy gate runs Alembic through revision `20260803_0012`, configures the three login roles, enables S3 versioning, and creates/verifies the Qdrant collection.

### AWS S3

Create a private bucket in the same or nearest practical region. Block all public access. The application enables versioning when `OBJECT_STORAGE_VERSIONING_MODE=managed`. Use a narrowly scoped IAM key that can access only the application bucket.

### Qdrant Cloud

Create a cluster and use separate staging and production collections. Configure the URL, API key, and collection name.

### SMTP

Configure a verified sender. For Resend SMTP, use its SMTP host, username, API-key password, and TLS port. Invitations, password reset, and email verification do not work until SMTP is configured.

## 3. Deploy staging backend on Render

Create a Blueprint from `render.yaml`. It creates two groups linked to both API and worker:

- `lsa-staging-generated-secrets` — Render generates the shared JWT, MFA/message-encryption and metrics secrets once.
- `lsa-staging-hosted-configuration` — populate this group in the Render dashboard before the first successful deploy. This prevents API/worker configuration drift.

| Category | Keys to add to the shared hosted-configuration group |
|---|---|
| URLs and web policy | `PUBLIC_APP_URL`, `TRUSTED_HOSTS`, `CORS_ALLOWED_ORIGINS`, `CONTENT_SECURITY_POLICY` |
| Neon | `DATABASE_URL`, `AUTH_DATABASE_URL`, `MIGRATION_DATABASE_URL`, `WORKER_DATABASE_URL`, `POSTGRES_APP_PASSWORD`, `POSTGRES_AUTH_PASSWORD`, `POSTGRES_WORKER_PASSWORD` |
| Object storage | `OBJECT_STORAGE_ENDPOINT`, `OBJECT_STORAGE_REGION`, `OBJECT_STORAGE_BUCKET`, `OBJECT_STORAGE_ACCESS_KEY`, `OBJECT_STORAGE_SECRET_KEY` |
| Qdrant | `QDRANT_URL`, `QDRANT_API_KEY` |
| AI providers | at least `GOOGLE_GEMINI_API_KEY`; optional `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `DEEPSEEK_API_KEY` |
| Email | `EMAIL_FROM_ADDRESS`, `SMTP_HOST`, `SMTP_USERNAME`, `SMTP_PASSWORD` |
| Staging seed only | `SEED_DEMO_PASSWORD` (strong random value; remove or rotate after acceptance) |

The Blueprint creates:

- `lsa-staging-api`
- `lsa-staging-worker`
- `lsa-staging-redis`
- `lsa-staging-clamav`

Staging intentionally starts with `ENABLE_DEMO_SEED=false` so the approved local-data import cannot collide with pre-created rows. After the approved relational/object/vector migration is complete, set `ENABLE_DEMO_SEED=true` for one redeploy and provide a strong random `SEED_DEMO_PASSWORD` in the shared hosted-configuration group. The idempotent seed creates or refreshes the two synthetic institutions and all eight approved test roles without copying local password hashes. Set `ENABLE_DEMO_SEED=false` again after the seed succeeds.

After deployment, verify:

```text
https://<RENDER_API_HOST>/health
https://<RENDER_API_HOST>/ready
https://<RENDER_API_HOST>/docs
```

## 4. Deploy frontend on Vercel

1. Import the same GitHub repository.
2. Set the Vercel **Root Directory** to `apps/web`.
3. Vercel uses `apps/web/vercel.json` and `npm ci`.
4. Configure:

```text
API_BASE_URL=https://<RENDER_API_HOST>
```

5. Update Render backend values:

```text
PUBLIC_APP_URL=https://<VERCEL_HOST>
CORS_ALLOWED_ORIGINS=https://<VERCEL_HOST>
TRUSTED_HOSTS=<RENDER_API_HOST>
```

6. Redeploy the API and frontend.

## 5. Verify authentication and controlled onboarding

The public identity experience is deliberately controlled:

- **Sign in** — existing user
- **Institution SSO** — preferred where configured
- **Accept invitation** — secure registration for an invited user
- **Request institutional access** — creates a pending request; it does not grant a role
- **No public self-assignment of privileged roles**

Test login, role selection, invitation acceptance, access requests, email verification, password reset, MFA, logout, session refresh, and external-access expiry.

## 6. Reproduce approved local data in staging

Do not copy the local database blindly. Use the controlled migration runbook:

1. Create or select a dedicated local migration-source database containing only approved tenant data. Set `APPROVED_TENANT_IDS` and `EXPORT_SOURCE_APPROVED=true`; the preflight refuses mixed or production sources.
2. Run `scripts/deployment/Export-ApprovedLocalData.ps1`.
3. Review and approve the generated manifest.
4. Run migrations against staging.
5. `scripts/deployment/Import-ApprovedData.ps1`
6. `scripts/deployment/migrate_object_versions.py`
7. `scripts/deployment/apply_storage_version_mapping.py`
8. Rebuild or migrate Qdrant using `scripts/deployment/migrate_qdrant.py`.
9. Start Redis clean.
10. Generate local and deployed parity manifests.
11. Run `scripts/deployment/verify_parity.py`.
12. Enable the staging seed for one deploy to regenerate secure test credentials, then disable it again.

The deployment is not accepted until application version, Alembic revision, schema/table inventory, role catalogue, permission catalogue, object checksums, Qdrant configuration, tenant isolation, authentication, and all eight staging workflows pass.

## 7. Deploy production

Use `render.production.yaml` only after staging acceptance.

Production enforces:

- `ENABLE_DEMO_SEED=false`
- no shared or known seed passwords
- no local sessions, reset tokens, invitations, Redis state, model binaries, or unapproved data
- separate Neon, S3, Qdrant, Redis, SMTP, AI-provider, and encryption credentials
- legal, privacy, institutional, and security approval before real-data onboarding

Temporary production smoke-test users must be created through the real invitation workflow and disabled after acceptance.

## 8. Mandatory release evidence

Retain a redacted release record containing:

- Git commit and container image digests
- Alembic revision
- staging/production parity manifests
- migration checksums
- role and tenant-isolation results
- login/onboarding results
- S3 object-version/checksum results
- Qdrant collection and point results
- all eight staging role workflows
- backup and restore-drill evidence
- secret-scan result

See `docs/operations/VERCEL_RENDER_NEON_DEPLOYMENT.md` and `docs/operations/DEPLOYMENT_PARITY_RUNBOOK.md` for the full procedure.
