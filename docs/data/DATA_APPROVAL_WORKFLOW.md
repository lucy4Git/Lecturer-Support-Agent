# Data Approval Workflow

**Project:** Lecturer Support Agent  
**Version:** 2.5.1  
**Date:** 2026-08-03

## Governance States

```
DISCOVERED → PENDING_RIGHTS_REVIEW → RIGHTS_VERIFIED → APPROVED_FOR_LOCAL
                                                      → APPROVED_FOR_STAGING
                                                      → APPROVED_FOR_PRODUCTION
                                                      → REJECTED
                     ↓
                  WITHDRAWN
                  EXPIRED
```

## Step-by-Step Approval for a New Dataset

### 1. Discovery
- Researcher identifies a potential source
- Add entry to `data/catalogue/dataset_catalogue.yaml` with `governance_state: DISCOVERED`
- Add stub row to `data/governance/rights_ledger.csv`

### 2. Rights Review
- Legal or Data Governance Lead reviews licence, terms of use, and robots.txt
- If rights are unclear → `PENDING_RIGHTS_REVIEW` (quarantined)
- If rights are clear → `RIGHTS_VERIFIED`

### 3. Local Approval
- Data Governance Lead reviews for personal information and confidentiality
- PII scan result documented
- Update `governance_state: APPROVED_FOR_LOCAL`
- Add approval row to `data/governance/approval_register.csv`
- Only clearly licensed public material may be automatically approved at this stage

### 4. Staging Approval
- Staging approval requires additional review by Data Governance Lead
- Confirm the dataset passes the ingestion pipeline dry-run
- Update `governance_state: APPROVED_FOR_STAGING`

### 5. Production Approval
- Requires explicit human decision — never automated
- Minimum 2 approvers for production (see `data/governance/approver_matrix.yaml`)
- Update `governance_state: APPROVED_FOR_PRODUCTION`
- Record approval reference in `approval_register.csv`

## Self-Approval Prohibition

Claude and automated pipelines must **never** self-approve:
- Institution-specific confidential data
- Any dataset in `PENDING_RIGHTS_REVIEW`
- Any production-environment dataset

## Rejection and Withdrawal

- `REJECTED`: dataset determined unsuitable; not for ingest
- `WITHDRAWN`: previously approved but rights revoked or issues found
- `EXPIRED`: approval period ended; must go through re-approval

On rejection/withdrawal: remove from Qdrant, PostgreSQL, and object storage; retain rights ledger entry.
