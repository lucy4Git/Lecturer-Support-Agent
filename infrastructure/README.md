# Infrastructure

Local containers, production orchestration, IaC, ingress, observability, secrets and backup.

Implementation must follow `PROJECT_CONSTITUTION.md`, requirements, ADRs and security rules.

## v1.3 local data foundation

`compose.yaml` defines PostgreSQL, Redis, MinIO and Qdrant. The corresponding contracts and bootstrap files are in `infrastructure/database/`. Services start only through an explicit developer command.
