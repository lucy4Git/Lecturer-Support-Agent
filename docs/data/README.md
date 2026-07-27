# Data Foundation and Model Readiness Pack

**Status:** Design baseline for review before database or model-adaptation implementation  
**Checkpoint:** DFMR-1  
**Updated:** 2026-07-21

This directory defines the data, database, governance, licensing, privacy, ingestion, versioning, source-integrity, evaluation and model-readiness requirements for the standalone Lecturer Support Agent.

## Binding principles

1. The product is multi-institutional. Tenant data must never be mixed by default.
2. The product provides high-quality generic AI assistance and does not require institutional grounding for every response.
3. Institutional materials are optional context and remain controlled by their institution.
4. Private institutional content and user conversations are **not model-training data by default**.
5. No source, author, DOI, policy, approval or compliance claim may be fabricated.
6. Every upload creates an auditable immutable version; no user's material is silently overwritten.
7. Dataset use requires recorded provenance, licence, permitted-purpose and retention decisions.
8. Evaluation data remains isolated from prompt-development, fine-tuning and production feedback datasets.
9. Model adaptation begins with prompting, tools and evaluation; fine-tuning requires an evidence-based approval gate.
10. Any implementation derived from this pack must be discussed with the project owner before coding.

## Pack contents

- [Data strategy](DATA_STRATEGY.md)
- [Data requirements catalogue](DATA_REQUIREMENTS_CATALOGUE.md)
- [Dataset acquisition plan](DATASET_ACQUISITION_PLAN.md)
- [Model adaptation strategy](MODEL_ADAPTATION_STRATEGY.md)
- [Database architecture](DATABASE_ARCHITECTURE.md)
- [Data governance](DATA_GOVERNANCE.md)
- [Data classification policy](DATA_CLASSIFICATION_POLICY.md)
- [Licensing and copyright](DATA_LICENSING_AND_COPYRIGHT.md)
- [Privacy and retention](DATA_PRIVACY_AND_RETENTION.md)
- [Institutional data onboarding](INSTITUTIONAL_DATA_ONBOARDING.md)
- [Bulk-upload scenarios](BULK_UPLOAD_SCENARIOS.md)
- [Document versioning standard](DOCUMENT_VERSIONING_STANDARD.md)
- [Source-verification data model](SOURCE_VERIFICATION_DATA_MODEL.md)
- [Evaluation dataset specification](EVALUATION_DATASET_SPECIFICATION.md)
- [AI safety and red-team dataset](AI_SAFETY_AND_RED_TEAM_DATASET.md)
- [Data traceability matrix](DATA_TRACEABILITY_MATRIX.md)
- [Candidate source register](DATA_SOURCE_REGISTER.md)
- [Validation report](DATA_FOUNDATION_VALIDATION_REPORT.md)

Machine-readable contracts are under `data/schemas/`; examples and the acquisition register are under `data/manifests/`; editable PlantUML diagrams are under `docs/architecture/uml/data-foundation/`.
