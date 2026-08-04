# Data Ingestion Runbook

**Project:** Lecturer Support Agent  
**Version:** 2.5.1  
**Date:** 2026-08-03

## Prerequisites

- Dataset has `governance_state` of `APPROVED_FOR_{ENV}`
- Approval recorded in `data/governance/approval_register.csv`
- Rights ledger entry present in `data/governance/rights_ledger.csv`
- Object storage configured and accessible
- Qdrant running and healthy
- PostgreSQL migration head at `20260726_0011`

## 20-Step Pipeline

```
python scripts/data/ingest_pipeline.py --dataset-id <DS-XXX> --env local
```

| Step | Name | Fail Behaviour |
|------|------|---------------|
| 1 | Source verification | ABORT |
| 2 | Licence verification | ABORT |
| 3 | Rights-status verification | ABORT |
| 4 | Approval-gate verification | ABORT |
| 5 | File download | ABORT |
| 6 | Malware scan | ABORT if REQUIRE_MALWARE_SCAN=true |
| 7 | File-type validation | ABORT |
| 8 | Duplicate detection | WARN |
| 9 | SHA-256 calculation | ABORT if mismatch |
| 10 | Metadata extraction | ABORT |
| 11 | PII scan | ABORT if personal data found |
| 12 | Confidentiality classification | ABORT if CONFIDENTIAL |
| 13 | Text extraction | WARN if unavailable |
| 14 | Chunking | WARN if unavailable |
| 15 | Embedding | WARN if model not configured |
| 16 | Qdrant indexing | ABORT |
| 17 | PostgreSQL registration | WARN |
| 18 | Object-storage registration | WARN |
| 19 | Audit-log creation | PASS |
| 20 | Rollback support | PASS |

## Rollback

```
python scripts/data/rollback_ingest.py --dataset-id <DS-XXX> --job-id <JOB_ID>
```

This removes Qdrant chunks, PostgreSQL records, and object-storage objects
for the specified ingestion job.

## Parity Verification

After ingestion, run:

```
python scripts/data/data_parity_verifier.py --env local
```

A non-zero exit code means the environment is not in a deployable state.

## Dry Run

```
python scripts/data/ingest_pipeline.py --dataset-id DS-003 --env local --dry-run
```
