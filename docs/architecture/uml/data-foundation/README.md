# Data Foundation PlantUML Diagrams

| Diagram | Purpose |
|---|---|
| `data_architecture.plantuml` | Polyglot persistence, service boundaries and tenant-scoped data controls. |
| `data_ingestion_sequence.plantuml` | End-to-end quarantine, validation, versioning, extraction and indexing. |
| `bulk_upload_sequence.plantuml` | Contextual bulk-upload permission and per-item outcomes. |
| `document_versioning_state.plantuml` | Immutable document-version lifecycle. |
| `source_verification_sequence.plantuml` | Claim-level source verification and citation eligibility. |
| `evaluation_data_flow.plantuml` | Separation of runtime, evaluation, red-team and possible future adaptation data. |

All sources are editable PlantUML. Rendered validation images, when generated, are stored in `../rendered/data-foundation/` and are not authoritative; the `.plantuml` files are authoritative.
