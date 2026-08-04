# Data Rights and Licensing

**Project:** Lecturer Support Agent  
**Version:** 2.5.1  
**Date:** 2026-08-03

## Licence Summary

| Dataset ID | Licence | Commercial Use | Training | Retrieval | Evaluation |
|-----------|---------|---------------|----------|-----------|------------|
| DS-001 | Various CC per item | CONDITIONAL | CONDITIONAL | YES | NO |
| DS-002 | CC BY-NC-SA 4.0 | NO | NO | YES | YES |
| DS-003 | CC BY 4.0 | YES | YES | YES | YES |
| DS-004 | CC0 1.0 | YES | YES | YES | YES |
| DS-005 | Crossref free / CC0 | CONDITIONAL | CONDITIONAL | NO | YES |
| DS-006 | PENDING REVIEW | PENDING | PENDING | NO | NO |
| DS-007 | Various (CC BY/NC) | CONDITIONAL | CONDITIONAL | CONDITIONAL | NO |
| DS-008 | CC BY-SA 3.0 IGO | YES | YES | YES | NO |
| DS-009 | Public Domain | YES | YES | YES | YES |
| DS-010 | MIT (internal) | YES | YES | YES | YES |
| DS-011 | MIT (internal) | YES | YES | NO | YES |
| DS-012 | PENDING REVIEW | NO | NO | NO | NO |

## Prohibited Actions

- Ingesting any dataset marked `PENDING_RIGHTS_REVIEW` without explicit legal approval
- Using NC-licensed material (DS-002) in commercial SaaS production
- Claiming CC0 permission for DS-005 full-text (only metadata is CC0)
- Removing attribution from CC BY material
- Generating synthetic licences or DOIs
- Training commercial models on NC-licensed content

## NC Licence Handling (DS-002 — MIT OCW)

MIT OCW uses CC BY-NC-SA 4.0. This means:

- **Local and staging:** permitted for non-commercial evaluation
- **Production commercial SaaS:** requires separate MIT licence negotiation
- **Retrieval in non-commercial deployment:** permitted with attribution

## Self-Approval Prohibition

Claude and automated pipelines must never self-approve:
- Institution-specific confidential data
- Any dataset in `PENDING_RIGHTS_REVIEW`
- Production-environment datasets

Only clearly licensed public or open material may be automatically classified as
eligible for local or staging review.
