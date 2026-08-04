# Data Retention Policy

**Project:** Lecturer Support Agent  
**Version:** 2.5.1  
**Date:** 2026-08-03

## Retention Periods

| Data Type | Retention Period | Authority |
|-----------|-----------------|-----------|
| Open/public datasets (DS-003, DS-009) | Indefinite while licence maintained | Data Governance Lead |
| NC-licensed datasets (DS-002) | 5 years | Data Governance Lead |
| API-sourced metadata (DS-004, DS-005) | 30-day cache; refresh on next ingest | Technical |
| Synthetic fixtures (DS-010, DS-011) | Indefinite | Project Owner |
| Approval register entries | 7 years | Compliance |
| Rights ledger entries | 10 years | Legal |
| Audit log entries | 5 years | Compliance |
| Personal user data (production) | Duration of employment + 1 year (or per institutional policy) | DPO |
| Session tokens | 24 hours (access) / 30 days (refresh) | Technical |
| Evaluation results | 2 years | Research |

## Review Schedule

The Data Governance Lead must review retention periods annually and:
- Update entries where licences have changed
- Expire datasets past their retention period
- Confirm alignment with applicable data protection law

## Automated Enforcement

The scheduled worker job `retention_enforcement` (see v2.4 implementation) runs
dry-run retention checks. Actual deletion requires manual confirmation by the
Data Governance Lead until live evidence is established.
