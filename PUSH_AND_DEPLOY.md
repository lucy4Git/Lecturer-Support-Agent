# Push and deploy — owner checklist

The application implementation is packaged. Your remaining actions require your private vendor accounts and therefore cannot be completed inside this ZIP.

1. Read `DEPLOYMENT_QUICKSTART.md`.
2. Create a private GitHub repository and push this folder.
3. Wait for CI, CodeQL, dependency review, secret scanning, TypeScript, Next.js build, tests, validators and container builds to pass.
4. Create separate staging resources in Neon, S3, Qdrant, Render and SMTP.
5. Sync `render.yaml`, populate the protected shared environment group, and deploy the backend/worker.
6. Import the same repository into Vercel with Root Directory `apps/web` and set only server-side `API_BASE_URL`.
7. Run the approved-data migration and parity runbook before accepting staging.
8. Create secure staging credentials for all eight roles, then disable demonstration seeding.
9. Validate login, invitation, access request, password recovery, MFA, uploads, AI, sources, moderation, exports and tenant isolation online.
10. Obtain institutional/legal/security approval and deploy production from the same validated release using `render.production.yaml` and separate credentials/data.

Never upload or commit a real `.env` file. Do not copy Redis state, session/token data, password hashes, local model binaries, or unapproved data.
