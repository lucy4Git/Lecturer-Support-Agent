# Data Privacy and Retention

## 1. Privacy posture

The Lecturer Support Agent is designed for teaching support, not surveillance. Collect the minimum personal information needed for identity, authorisation, assignment, collaboration and audit. Do not use private institutional content or conversations for model training by default.

## 2. Privacy roles and records

Each tenant identifies a data controller/owner and approved processors. The platform maintains processing purpose, data categories, recipients, location, retention, security, legal basis where required and subject-right procedures.

## 3. Personal-data minimisation

Prefer stable internal IDs over national identifiers. Store only necessary contact and employment/academic-role data. Avoid student records during the initial implementation. Where examples require student context, use synthetic or de-identified data.

## 4. Conversation privacy

- conversations are tenant and user scoped;
- sharing is explicit;
- model-provider payloads contain minimum necessary context;
- raw content is excluded from general logs;
- feedback does not imply training consent;
- retention is configurable by tenant and content class;
- deletion requests are reconciled with legitimate audit and legal-hold needs.

## 5. External users

External moderators and reviewers receive named, time-limited access to assigned resources only. Their uploads, views, downloads and comments are audited. Access expiration removes active permissions without deleting historical review evidence.

## 6. Recommended retention baseline

Final periods must be configured by institution and jurisdiction.

| Record | Baseline | Notes |
|---|---|---|
| Account and role assignment | active + institutional archive period | preserve effective history |
| Conversation | tenant-configured, e.g. 1–3 years | user deletion and legal hold supported |
| Generated teaching artifact | linked academic period + archive | user/institution policy |
| Active assessment and memorandum | secure period through release/moderation | stricter controls |
| Upload batch processing data | 1 year | retain errors/provenance longer if needed |
| Content versions | institutional academic-record period | immutable until authorised purge |
| Security audit | 2–7 years depending on policy | tamper-evident |
| AI execution metadata | 90 days–2 years | minimise prompt/output content |
| Temporary external grant | assignment + audit archive | permission expires automatically |
| Evaluation benchmark | project life + archival review | contains no uncontrolled personal data |
| Quarantined rejected file | 7–30 days | purge unless incident/legal hold |

## 7. Deletion and archival

Logical deletion removes normal visibility and creates a tombstone. Physical purge follows approval, checks for legal hold, removes object versions and indexes, records completion and propagates provider deletion where applicable. Referential audit records retain only minimum non-content evidence.

## 8. De-identification

De-identification removes direct identifiers, rare combinations, free-text identifiers and embedded document metadata. Re-identification risk is assessed. Pseudonymisation alone is not treated as anonymous data.

## 9. Cross-border and provider processing

Before enabling an external AI, OCR, transcription or analytics provider, record processing location, subprocessors, retention, training use, security commitments and deletion support. A tenant may restrict providers or regions.

## 10. Privacy tests

- user cannot view another tenant’s conversation;
- HOD access remains within assigned department scope;
- external reviewer access expires and cannot be refreshed without approval;
- exported content excludes hidden metadata not authorised for the recipient;
- model-provider payload blocks restricted data classes;
- deletion removes searchable/vector/object copies;
- analytics contain no identifiable prompts unless specifically authorised.
