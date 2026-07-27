# Data Traceability Matrix

| ID | Requirement | Design/Schema | UML | Implementation owner | Verification |
|---|---|---|---|---|---|
| DF-001 | Generic AI works without institutional data | `DATA_STRATEGY.md`, `MODEL_ADAPTATION_STRATEGY.md` | `source_verification_sequence.plantuml` | AI Orchestrator | Generic-response benchmarks |
| DF-002 | Institutional data optional and scoped | `DATABASE_ARCHITECTURE.md`, `DATA_GOVERNANCE.md` | `data_architecture.plantuml` | Tenant/Content services | Tenant retrieval tests |
| DF-003 | No tenant content training by default | `MODEL_ADAPTATION_STRATEGY.md`, `DATA_PRIVACY_AND_RETENTION.md` | `evaluation_data_flow.plantuml` | AI Governance | Provider payload and dataset audits |
| DF-004 | Complete dataset metadata | `dataset_manifest.schema.json` | `data_ingestion_sequence.plantuml` | Data Platform | JSON Schema validation |
| DF-005 | Immutable content versions | `DOCUMENT_VERSIONING_STANDARD.md`, `document_version.schema.json` | `document_versioning_state.plantuml` | Version/Provenance | Version integrity tests |
| DF-006 | Bulk upload for authorised roles | `BULK_UPLOAD_SCENARIOS.md`, `bulk_upload_manifest.schema.json` | `bulk_upload_sequence.plantuml` | Bulk Ingestion | Role-specific E2E tests |
| DF-007 | No silent overwrite | `DOCUMENT_VERSIONING_STANDARD.md` | `document_versioning_state.plantuml` | Version/Provenance | Concurrent and duplicate tests |
| DF-008 | Configurable HEI hierarchy | `institutional_structure.schema.json` | `data_architecture.plantuml` | Tenant/Organisation | Hierarchy fixtures and cycle tests |
| DF-009 | Robust multi-store database | `DATABASE_ARCHITECTURE.md` | `data_architecture.plantuml` | Platform Architecture | Load, failover and restore tests |
| DF-010 | Item-level rights and permitted purpose | `DATA_LICENSING_AND_COPYRIGHT.md`, `dataset_manifest.schema.json` | `data_ingestion_sequence.plantuml` | Data Governance | Rights-gate tests |
| DF-011 | Privacy and retention | `DATA_PRIVACY_AND_RETENTION.md`, `document_metadata.schema.json` | `document_versioning_state.plantuml` | Privacy/Data | Deletion and retention tests |
| DF-012 | Verified source cards only | `SOURCE_VERIFICATION_DATA_MODEL.md`, `source_record.schema.json`, `citation_record.schema.json` | `source_verification_sequence.plantuml` | Source Verification | Fabricated-source suite |
| DF-013 | Evaluation isolation | `EVALUATION_DATASET_SPECIFICATION.md`, `evaluation_case.schema.json` | `evaluation_data_flow.plantuml` | Model Evaluation | Contamination checks |
| DF-014 | Safety/red-team coverage | `AI_SAFETY_AND_RED_TEAM_DATASET.md`, `evaluation_case.schema.json` | `evaluation_data_flow.plantuml` | Security/AI Safety | Release red-team gate |
| DF-015 | Institution onboarding | `INSTITUTIONAL_DATA_ONBOARDING.md`, `institutional_structure.schema.json` | `data_ingestion_sequence.plantuml` | Institution Admin/Platform | Pilot reconciliation report |
| DF-016 | Independent administrator and HOD roles | `DATA_GOVERNANCE.md`, existing role matrix | `bulk_upload_sequence.plantuml` | IAM | Scope and separation tests |
| DF-017 | Historical provenance retained | `DOCUMENT_VERSIONING_STANDARD.md`, `document_version.schema.json` | `document_versioning_state.plantuml` | Audit/Version | Provenance chain tests |
| DF-018 | Multi-device resumable upload | `BULK_UPLOAD_SCENARIOS.md` | `bulk_upload_sequence.plantuml` | Web/Bulk Ingestion | Network interruption E2E |
| DF-019 | Model adaptation evidence gate | `MODEL_ADAPTATION_STRATEGY.md` | `evaluation_data_flow.plantuml` | AI Governance | Baseline comparison report |
| DF-020 | Data pack validation | `DATA_FOUNDATION_VALIDATION_REPORT.md` | all new UML | Architecture/QA | Validation script |
