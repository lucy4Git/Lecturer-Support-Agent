# Institutional User Onboarding

**Project:** Lecturer Support Agent  
**Version:** 2.5.1  
**Date:** 2026-08-03

## Approved Onboarding Methods

Real institutional users must be obtained through **one** of these approved methods:

1. Institution-provided CSV using `data/templates/institutional_users.template.csv`
2. Microsoft Entra ID (OIDC/SAML)
3. Google Workspace (OIDC)
4. Authorised institutional directory integration
5. OneRoster where supported
6. Approved HR or academic-management integration
7. Controlled administrator invitation
8. Administrator-reviewed access request

## Prohibited Methods

- Scraping individuals from the internet
- Creating accounts from public staff directories
- Using LinkedIn, institutional websites, or email harvesting
- Importing without data-processing authority

## Template Usage

1. Copy `data/templates/institutional_users.template.csv`
2. Replace all `REPLACE_*` placeholders with real values
3. Never commit the completed file to Git
4. Submit to an authorised approver for review (see `data/governance/approver_matrix.yaml`)
5. Receive approval reference before importing
6. Import via `scripts/data/import_institutional_users.py --file <path> --env <env>`
7. Store the approval reference in `data/governance/approval_register.csv`

## Eight Synthetic Roles (Local and Staging)

For local development and staging validation, the seed script creates eight
synthetic accounts only. These use:

- Synthetic names and synthetic institution (`demo-north`)
- Unique temporary credentials (generated per run)
- No shared known password committed to Git
- Credential stored in `runtime/seed_credentials.txt` (gitignored)

Production refuses synthetic seed unless an explicitly isolated demonstration
tenant is authorised.

## Data Processing Authority

Every real user import requires a stated lawful basis. Accepted bases:

- GDPR Article 6(1)(b) — performance of a contract
- GDPR Article 6(1)(c) — legal obligation
- GDPR Article 6(1)(e) — public task
- Equivalent national data-protection basis

Record the authority in the `data_processing_authority` column of the import file.
