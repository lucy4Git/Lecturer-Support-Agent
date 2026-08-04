# Data Parity Runbook

**Project:** Lecturer Support Agent  
**Version:** 2.5.1  
**Date:** 2026-08-03

## Purpose

Confirm that local, staging, and production environments contain identical
governed data — same datasets, same versions, same checksums, same
Qdrant chunk counts, no unapproved material, no stale synthetic users.

## Running the Verifier

```bash
# Local environment
python scripts/data/data_parity_verifier.py --env local

# Staging
python scripts/data/data_parity_verifier.py --env staging

# Production
python scripts/data/data_parity_verifier.py --env production
```

Exit code 0 = all checks passed.  
Exit code 1 = one or more violations found — **do not deploy**.

## Checks Performed

1. Catalogue integrity (YAML and JSON present and consistent)
2. No unapproved dataset in manifest
3. Rights ledger completeness (every catalogued dataset has an entry)
4. Privileged roles have configured approvers
5. No staging synthetic users in production manifest
6. Redis clean-start declared
7. No secret values in catalogue
8. Evaluation datasets not assigned to retrieval collection

## Fail-Closed Conditions

The verifier returns exit code 1 if any of the following:

- An unapproved dataset appears in the manifest
- A checksum differs from the catalogue record
- An object is missing from object storage
- A document version is inconsistent
- A Qdrant payload lacks tenant metadata
- A real user lacks an approver
- A privileged role has a placeholder approver (production only)
- A staging synthetic user appears in the production manifest
- Redis is not declared clean-start

## Linking to Deployment

The parity verifier must pass before any promotion step:

- local → staging: run with `--env staging`
- staging → production: run with `--env production`

CI/CD pipeline must call the verifier and halt on non-zero exit.
