# Data Governance

## 1. Governance objective

Ensure every use of data is authorised, necessary, traceable, secure, high quality and aligned with the Lecturer Support Agent’s teaching-support scope.

## 2. Governance roles

| Role | Accountability |
|---|---|
| Project Owner | Approves product-level scope and major implementation decisions |
| Institutional Data Owner | Authorises purpose, access and retention for tenant data |
| Data Steward | Metadata, quality, catalogue and issue resolution |
| Academic SME | Pedagogical and discipline validity |
| Institution Administrator | Operational onboarding and authorised bulk administration |
| Head of Department | Departmental content, course allocation and oversight within scope |
| Security Officer | Security classification, controls and incident handling |
| Privacy Officer | lawful basis, notices, subject rights and data minimisation |
| Model Evaluation Lead | benchmark isolation, release gates and contamination controls |
| Data Engineer | pipelines, validation, lineage and reliability |
| AI/ML Engineer | model-use documentation and controlled experiments |

The Head of Department and Institution Administrator are independent roles. Governance responsibilities do not grant access outside their assigned scopes.

## 3. Data decision record

Every dataset receives a record containing owner, steward, purpose, source, licence, legal basis where relevant, tenant, data classes, permitted uses, prohibited uses, retention, quality thresholds, processors, location, risks, approval and review date.

## 4. Permitted-use classes

- `DISCOVERY_METADATA`
- `RUNTIME_RETRIEVAL`
- `USER_REQUEST_PROCESSING`
- `INSTITUTIONAL_ANALYTICS`
- `DEIDENTIFIED_PRODUCT_ANALYTICS`
- `EVALUATION_ONLY`
- `SAFETY_TESTING_ONLY`
- `PROMPT_EXAMPLES`
- `MODEL_ADAPTATION`
- `ARCHIVE_ONLY`

Permission for one class never implies another.

## 5. Data council decisions

The project owner and relevant reviewers must approve:

- adding a new sensitive data class;
- using tenant content for model adaptation;
- cross-border or new-provider processing;
- adding a public data source with uncertain rights;
- changing retention of confidential assessments;
- enabling cross-tenant benchmarking;
- publishing derived datasets;
- changing canonical institutional content in bulk;
- releasing a model with material benchmark regression.

## 6. Quality governance

Data stewards maintain quality dashboards for completeness, validity, uniqueness, consistency, freshness, provenance and bias coverage. Critical defects block indexing or model use. Corrections create new versions; original records remain in lineage.

## 7. Access governance

Access is granted by role, tenant, organisational scope, resource, purpose and time. Temporary external reviewer and moderator grants are explicit, task-bound, expiring and audited. Bulk upload is a capability surfaced to any authorised role, not a global role entitlement.

## 8. Model-use governance

Model calls record the approved model, prompt version, tools, data classes sent, source evidence, policy decision and output validation status. Provider logs must not contain more content than necessary. Institutional data is not used to improve provider models unless contractually prohibited from such use and explicitly approved.

## 9. Transparency

Users can see whether an output is generic, institution-informed or source-verified. They can inspect source cards, limitations and generated status. The system must never imply that AI-generated material is institutionally approved without human action.

## 10. Incident governance

Data incidents include tenant leakage, unauthorised source display, confidential assessment exposure, malicious upload, lost provenance, model-training misuse and inability to honour deletion. Incidents follow containment, evidence preservation, assessment, notification, remediation and post-incident review.

## 11. Review cadence

- critical datasets and model providers: quarterly;
- source licences and external APIs: at least semi-annually or on detected change;
- institutional policies: on effective-date change;
- evaluation coverage: every release;
- retention and legal holds: annually;
- external access grants: continuous expiry enforcement.

## 12. Governance evidence

Required evidence includes dataset cards, data-processing records, approval decisions, lineage, validation results, access logs, quality reports, benchmark runs, deletion records, incident records and change history.
