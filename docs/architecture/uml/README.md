# PlantUML Diagram Index

All UML files use editable PlantUML source with the `.plantuml` extension. Generated images are non-authoritative derivatives.

## Core architecture

- `context/01_system_context.plantuml`
- `architecture/01_system_architecture.plantuml`
- `architecture/02_container_view.plantuml`
- `architecture/03_multi_provider_ai_gateway.plantuml`
- `use-cases/01_role_use_cases.plantuml`
- `data/01_erd.plantuml`
- `classes/01_domain_class_model.plantuml`
- `components/01_component_diagram.plantuml`
- `deployment/01_deployment_diagram.plantuml`
- `data-flow/01_data_flow.plantuml`
- `activities/01_unified_request_activity.plantuml`
- `activities/02_bulk_upload_activity.plantuml`
- `states/01_content_version_lifecycle.plantuml`
- `states/02_review_assignment_lifecycle.plantuml`
- Sequence diagrams in `sequences/`, including `sequences/11_model_routing_and_fallback.plantuml`.

## Data Foundation and Model Readiness

See `data-foundation/README.md` for:

- Data architecture
- Ingestion sequence
- Permission-aware bulk upload
- Immutable version lifecycle
- Claim-to-source verification
- Evaluation data flow

Render using a current local PlantUML installation or IDE extension. Store generated images under `rendered/`.

## Implemented v1.3 diagrams

See [`v1.3/README.md`](v1.3/README.md) for the physical database, RLS, immutable upload, academic assignment, external access and data-component diagrams.

- [`v1.7/README.md`](v1.7/README.md) — teaching-output production, inline versions, assessment safety, module context and exports.

- [`v1.9/`](v1.9/README.md) — Departmental teaching operations, readiness, workload, calendar, handover and operational dashboards.

- [`v2.1/README.md`](v2.1/README.md) — commercial unified workspace, authorised search, Library and Files attachment, exact-version saved outputs, notifications, and responsive navigation.
