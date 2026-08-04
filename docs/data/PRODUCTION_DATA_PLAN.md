# Production Data Plan

**Project:** Lecturer Support Agent  
**Version:** 2.5.1  
**Date:** 2026-08-03

## Governing Rule

Production must contain **only** approved institutional users, approved datasets,
and approved configuration. No synthetic seed users. No demo accounts unless
an explicitly isolated demonstration tenant is authorised.

## Production Dataset Requirements

All production datasets must:
1. Have `governance_state: APPROVED_FOR_PRODUCTION`
2. Have at least 2 approvers recorded in `approval_register.csv`
3. Have verified SHA-256 checksums
4. Pass the ingestion pipeline with no warnings on PII or confidentiality
5. Be ingested from approved object storage — NOT re-downloaded from source
6. Have Qdrant payloads including tenant ID, dataset ID, rights status

## Production Users

- No auto-seeded or synthetic users
- Only invitation-created, SSO-provisioned, or import-approved users
- Each user record must have a data-processing authority stated
- Import manifest must be approved by Admin + Privacy Officer

## Production Checklist

- [ ] Complete production manifest from `production_data_manifest.template.json`
- [ ] Replace ALL `REPLACE_WITH_*` placeholders
- [ ] Run `data_parity_verifier.py --env production` — must return exit code 0
- [ ] Confirm `ENABLE_DEMO_SEED=false` in environment
- [ ] Confirm `synthetic_seed_disabled=true` in manifest
- [ ] Confirm no staging users in production manifest
- [ ] Confirm Redis starts clean
- [ ] Two authorised humans sign the production-release approval
- [ ] Record approval references
- [ ] Push manifest hash to deployment record

## Prohibited in Production

- `ENABLE_DEMO_SEED=true`
- Synthetic seed users
- Shared known passwords
- Plaintext credentials
- Local `.env` files
- Database dumps from staging
- Object-storage exports from staging
- Qdrant snapshots containing unapproved data
