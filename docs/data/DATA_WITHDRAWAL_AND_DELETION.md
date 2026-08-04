# Data Withdrawal and Deletion

**Project:** Lecturer Support Agent  
**Version:** 2.5.1  
**Date:** 2026-08-03

## When to Withdraw a Dataset

A dataset must be withdrawn when:
- The copyright holder revokes the licence
- Rights review determines the dataset was incorrectly approved
- A data protection authority issues a removal order
- The dataset is found to contain personal information not previously identified
- The retention period expires

## Withdrawal Steps

1. Update `governance_state` to `WITHDRAWN` in `data/catalogue/dataset_catalogue.yaml`
2. Update the rights ledger with withdrawal date and reason
3. Remove all Qdrant chunks for the dataset:
   ```
   python scripts/data/rollback_ingest.py --dataset-id <DS-XXX> --env <env>
   ```
4. Delete object-storage files for the dataset
5. Mark PostgreSQL metadata records as `withdrawn`
6. Re-run data parity verifier to confirm clean state
7. Retain the rights ledger entry (for audit trail)
8. Update the dataset catalogue entry with withdrawal instructions

## Hard Deletion (GDPR / Legal Order)

For hard deletion of personal data under GDPR Article 17 or a legal order:
1. Follow the same steps as withdrawal
2. Additionally: delete PostgreSQL metadata record (not just mark as withdrawn)
3. Overwrite the object-storage slot (do not rely on logical delete)
4. Document the deletion in the privacy register

## Retention on Withdrawal

- Rights ledger entry: retained indefinitely (audit trail)
- Catalogue entry: retained with `WITHDRAWN` state (audit trail)
- Actual data files: deleted
- Qdrant chunks: deleted
- Object-storage objects: deleted
- PostgreSQL records: marked withdrawn (or hard-deleted per above)
