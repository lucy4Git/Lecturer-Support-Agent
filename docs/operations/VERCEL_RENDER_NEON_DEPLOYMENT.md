# Vercel, Render, Neon and managed-services deployment

## Approved topology

```text
Browser
  └─ Vercel: Next.js web/BFF
       └─ HTTPS → Render: FastAPI API
                    ├─ Render background worker
                    ├─ Render Key Value (temporary Redis state)
                    ├─ Render private ClamAV
                    ├─ Neon PostgreSQL (authoritative, RLS)
                    ├─ AWS S3 (versioned files/exports)
                    ├─ Qdrant Cloud (tenant-filtered vectors)
                    ├─ SMTP provider
                    └─ Governed AI providers
```

Vercel and Render deploy the same Git commit. Neon migrations, role catalogue, and data manifests are part of the release gate.

## Environment boundaries

| Item | Local | Staging | Production |
|---|---|---|---|
| Source/migrations | same validated chain | same commit/image | same promoted image |
| PostgreSQL | local container | separate Neon DB | separate Neon DB |
| Demo seed | opt-in | disabled during import; enabled once after migration | prohibited |
| Object storage | MinIO | separate S3 bucket | separate S3 bucket |
| Qdrant | local | separate collection/cluster | separate collection/cluster |
| Redis | local | clean Render Key Value | clean Render Key Value |
| Credentials | local `.env` only | Render/Vercel secrets | protected production secrets |

## Render API and worker

`render.yaml` is the staging Blueprint. `render.production.yaml` is the production template. Both use Docker to preserve runtime parity. Each Blueprint creates a generated-secret group for JWT, MFA/message encryption and metrics, plus an empty hosted-configuration group that the owner populates once in the Render dashboard. Both groups are linked to API and worker so database, storage, Qdrant, AI and SMTP values cannot drift between services. The API service alone runs the pre-deploy gate; the worker must not race a second migration. Staging seeding is disabled during the approved-data import and is enabled only once afterwards with a secret-manager `SEED_DEMO_PASSWORD`.

The pre-deploy gate:

1. validates production/staging settings;
2. runs `alembic upgrade head`;
3. configures `lsa_app`, `lsa_auth`, and `lsa_worker` as least-privilege login roles;
4. creates/verifies S3 bucket versioning;
5. creates/verifies the Qdrant collection and vector dimension;
6. seeds synthetic users only when staging explicitly enables it after approved data import.


### Render shared hosted-configuration group

Before the first successful deploy, populate the environment-specific `*-hosted-configuration` group with the URL/credential keys listed in `DEPLOYMENT_QUICKSTART.md`. Do not add secret values to `render.yaml`. Render preserves dashboard-added variables that the Blueprint omits. Staging and production use separate groups and values.

## Neon role model

- Neon owner/migration role: schema migration and role administration only
- `lsa_app`: tenant-owned application operations with forced RLS
- `lsa_auth`: narrowly scoped public authentication/onboarding operations
- `lsa_worker`: background jobs under tenant context

The API must never use the owner connection string. Use pooled Neon URLs for runtime roles and the direct URL for Alembic. Every URL must require SSL.

## Vercel web application

Set the project Root Directory to `apps/web`. Configure `API_BASE_URL` as a server-only environment variable. The frontend uses HTTP-only secure cookies through the Next.js backend-for-frontend routes; cloud AI keys and database credentials do not belong in Vercel.

## Cloud embeddings

Local development can use Ollama. Hosted deployments can set:

```text
EMBEDDING_PROVIDER=google_gemini
GOOGLE_GEMINI_EMBEDDING_MODEL=gemini-embedding-2
EMBEDDING_DIMENSION=768
```

or:

```text
EMBEDDING_PROVIDER=openai
OPENAI_EMBEDDING_MODEL=text-embedding-3-small
EMBEDDING_DIMENSION=768
```

The collection dimension and embedding response are checked before indexing.

## Object storage

AWS S3 is the recommended default because the application requires exact object versions and controlled version deletion. Use:

```text
OBJECT_STORAGE_VERSIONING_MODE=managed
```

A provider whose object history is always enabled can use `provider_enforced` only after its S3 compatibility is validated for listing, retrieving, and deleting exact versions. Cloudflare R2 is not an approved default for this release because the application requires bucket-versioning operations that are not fully supported by R2's S3 compatibility layer.

## Registration and sign-in

The production approach is:

1. institutional OIDC SSO;
2. administrator invitation and acceptance;
3. administrator-reviewed access request;
4. local email/password fallback where allowed.

A request-access submission is not a registration and does not grant a role. The Institution Administrator reviews it and sends a scoped invitation.

## Production refusal conditions

Deployment must fail or remain unaccepted when:

- migration revision differs;
- RLS policies are missing;
- role/permission catalogue differs;
- object storage is not versioned;
- Qdrant dimension differs;
- demo seeding is enabled in production;
- rate limiting or malware scanning is fail-open;
- required encryption keys are absent;
- API/worker use the owner database role;
- local secrets or exposed passwords are present;
- staging parity or eight-role workflows fail.
