# Documentation Index

This index is the primary navigation entry for the Lecturer Support Agent documentation set.

## Governance and product

- [`PROJECT_CONSTITUTION.md`](../PROJECT_CONSTITUTION.md)
- [`docs/governance/DECISION_REGISTER.md`](governance/DECISION_REGISTER.md)
- [`docs/governance/GLOSSARY.md`](governance/GLOSSARY.md)
- [`docs/blueprints/LECTURER_SUPPORT_AGENT_MASTER_BLUEPRINT.md`](blueprints/LECTURER_SUPPORT_AGENT_MASTER_BLUEPRINT.md)
- [`docs/product/PRODUCT_SCOPE.md`](product/PRODUCT_SCOPE.md)
- [`docs/product/PERSONAS_AND_JOBS_TO_BE_DONE.md`](product/PERSONAS_AND_JOBS_TO_BE_DONE.md)
- [`docs/product/COMMERCIAL_READINESS.md`](product/COMMERCIAL_READINESS.md)

## Requirements

- [`docs/requirements/FUNCTIONAL_REQUIREMENTS.md`](requirements/FUNCTIONAL_REQUIREMENTS.md)
- [`docs/requirements/NON_FUNCTIONAL_REQUIREMENTS.md`](requirements/NON_FUNCTIONAL_REQUIREMENTS.md)
- [`docs/requirements/ROLE_PERMISSION_MATRIX.md`](requirements/ROLE_PERMISSION_MATRIX.md)
- [`docs/requirements/BULK_UPLOAD_SCENARIOS.md`](requirements/BULK_UPLOAD_SCENARIOS.md)
- [`docs/requirements/USE_CASE_CATALOGUE.md`](requirements/USE_CASE_CATALOGUE.md)
- [`docs/requirements/ACCEPTANCE_CRITERIA.md`](requirements/ACCEPTANCE_CRITERIA.md)
- [`docs/requirements/REQUIREMENTS_TRACEABILITY_MATRIX.md`](requirements/REQUIREMENTS_TRACEABILITY_MATRIX.md)

## Architecture and UML

- [`docs/architecture/SYSTEM_ARCHITECTURE.md`](architecture/SYSTEM_ARCHITECTURE.md)
- [`docs/architecture/ARCHITECTURE_PRINCIPLES.md`](architecture/ARCHITECTURE_PRINCIPLES.md)
- [`docs/architecture/MULTI_TENANCY_AND_ORG_HIERARCHY.md`](architecture/MULTI_TENANCY_AND_ORG_HIERARCHY.md)
- [`docs/architecture/uml/README.md`](architecture/uml/README.md)
- [`docs/architecture/uml/data-foundation/README.md`](architecture/uml/data-foundation/README.md)
- [`docs/architecture/adr/README.md`](architecture/adr/README.md)

## Data Foundation and Model Readiness Pack

Read in this order:

1. [`DATA_STRATEGY.md`](data/DATA_STRATEGY.md)
2. [`DATA_REQUIREMENTS_CATALOGUE.md`](data/DATA_REQUIREMENTS_CATALOGUE.md)
3. [`DATASET_ACQUISITION_PLAN.md`](data/DATASET_ACQUISITION_PLAN.md)
4. [`DATA_SOURCE_REGISTER.md`](data/DATA_SOURCE_REGISTER.md)
5. [`MODEL_ADAPTATION_STRATEGY.md`](data/MODEL_ADAPTATION_STRATEGY.md)
6. [`DATABASE_ARCHITECTURE.md`](data/DATABASE_ARCHITECTURE.md)
7. [`DATA_GOVERNANCE.md`](data/DATA_GOVERNANCE.md)
8. [`DATA_CLASSIFICATION_POLICY.md`](data/DATA_CLASSIFICATION_POLICY.md)
9. [`DATA_LICENSING_AND_COPYRIGHT.md`](data/DATA_LICENSING_AND_COPYRIGHT.md)
10. [`DATA_PRIVACY_AND_RETENTION.md`](data/DATA_PRIVACY_AND_RETENTION.md)
11. [`INSTITUTIONAL_DATA_ONBOARDING.md`](data/INSTITUTIONAL_DATA_ONBOARDING.md)
12. [`BULK_UPLOAD_SCENARIOS.md`](data/BULK_UPLOAD_SCENARIOS.md)
13. [`DOCUMENT_VERSIONING_STANDARD.md`](data/DOCUMENT_VERSIONING_STANDARD.md)
14. [`SOURCE_VERIFICATION_DATA_MODEL.md`](data/SOURCE_VERIFICATION_DATA_MODEL.md)
15. [`EVALUATION_DATASET_SPECIFICATION.md`](data/EVALUATION_DATASET_SPECIFICATION.md)
16. [`AI_SAFETY_AND_RED_TEAM_DATASET.md`](data/AI_SAFETY_AND_RED_TEAM_DATASET.md)
17. [`DATA_TRACEABILITY_MATRIX.md`](data/DATA_TRACEABILITY_MATRIX.md)
18. [`DATA_FOUNDATION_VALIDATION_REPORT.md`](data/DATA_FOUNDATION_VALIDATION_REPORT.md)

Schema and example assets are indexed in [`data/README.md`](../data/README.md).


## Multi-Provider AI and Local Model Pack

- [`MULTI_PROVIDER_MODEL_STRATEGY.md`](ai/MULTI_PROVIDER_MODEL_STRATEGY.md)
- [`MODEL_ROUTING_AND_FALLBACK.md`](ai/MODEL_ROUTING_AND_FALLBACK.md)
- [`LOCAL_MODEL_AND_OLLAMA_GOVERNANCE.md`](ai/LOCAL_MODEL_AND_OLLAMA_GOVERNANCE.md)
- [`PROVIDER_DATA_HANDLING_MATRIX.md`](ai/PROVIDER_DATA_HANDLING_MATRIX.md)
- [`OLLAMA_WINDOWS_SETUP.md`](operations/OLLAMA_WINDOWS_SETUP.md)
- [`MODEL_DOWNLOAD_STORAGE_AND_UPDATES.md`](operations/MODEL_DOWNLOAD_STORAGE_AND_UPDATES.md)
- [`MULTI_PROVIDER_VALIDATION_REPORT.md`](ai/MULTI_PROVIDER_VALIDATION_REPORT.md)
- [`ADR-006`](architecture/adr/ADR-006-multi-provider-and-ollama-model-fabric.md)
- [`Provider registry`](../config/ai/providers.example.json)
- [`Ollama model profiles`](../config/ai/ollama-model-profiles.json)
- [`Model registry`](../config/ai/model-registry.example.json)

## UX, AI, security, testing, implementation and operations

- [`docs/ux/UNIFIED_AI_WORK_AREA.md`](ux/UNIFIED_AI_WORK_AREA.md)
- [`docs/ai/AI_ORCHESTRATION.md`](ai/AI_ORCHESTRATION.md)
- [`docs/security/SECURITY_ARCHITECTURE.md`](security/SECURITY_ARCHITECTURE.md)
- [`docs/testing/TEST_STRATEGY.md`](testing/TEST_STRATEGY.md)
- [`docs/implementation/IMPLEMENTATION_ROADMAP.md`](implementation/IMPLEMENTATION_ROADMAP.md)
- [`docs/operations/DEPLOYMENT_GUIDE.md`](operations/DEPLOYMENT_GUIDE.md)

The complete authoritative file inventory is maintained in [`PROJECT_FILE_MANIFEST.md`](../PROJECT_FILE_MANIFEST.md).

## v1.3 Physical Data and Database Foundation

- [`Phase 2 implementation report`](implementation/PHASE_2_V1.3_IMPLEMENTATION_REPORT.md)
- [`Physical database schema`](data/PHYSICAL_DATABASE_SCHEMA_V1.3.md)
- [`PostgreSQL RLS implementation`](security/POSTGRESQL_RLS_IMPLEMENTATION.md)
- [`Local database setup`](operations/V1.3_LOCAL_DATABASE_SETUP.md)
- [`API foundation`](api/V1.3_API_FOUNDATION.md)
- [`Database test evidence`](testing/V1.3_DATABASE_TEST_EVIDENCE.md)
- [`Dataset acquisition execution framework`](data/DATASET_ACQUISITION_EXECUTION_FRAMEWORK.md)
- [`ADR-007`](architecture/adr/ADR-007-polyglot-data-foundation.md)
- [`v1.3 PlantUML diagrams`](architecture/uml/v1.3/README.md)

## v1.4 Identity, Administration, and HOD Foundation

- [`Phase 3 implementation report`](implementation/PHASE_3_V1.4_IMPLEMENTATION_REPORT.md)
- [`Authentication and session security`](security/AUTHENTICATION_AND_SESSION_SECURITY_V1.4.md)
- [`Identity and administration API`](api/V1.4_IDENTITY_ADMINISTRATION_API.md)
- [`Unified role-aware shell`](ux/V1.4_UNIFIED_ROLE_AWARE_SHELL.md)
- [`v1.4 acceptance criteria`](requirements/V1.4_ACCEPTANCE_CRITERIA.md)
- [`Static validation evidence`](testing/V1.4_STATIC_VALIDATION_EVIDENCE.md)
- [`Release validation report`](testing/V1.4_RELEASE_VALIDATION_REPORT.md)
- [`Release checksums`](testing/V1.4_RELEASE_CHECKSUMS.sha256)
- [`Owner-machine validation`](operations/V1.4_OWNER_MACHINE_VALIDATION.md)
- [`ADR-008`](architecture/adr/ADR-008-active-role-session-and-bff.md)
- [`v1.4 PlantUML diagrams`](architecture/uml/v1.4/README.md)

## v1.5 Unified AI Conversation Engine

- [`Phase 4 implementation report`](implementation/PHASE_4_V1.5_IMPLEMENTATION_REPORT.md)
- [`Unified conversation API`](api/V1.5_UNIFIED_AI_CONVERSATION_API.md)
- [`Unified conversation engine`](ai/UNIFIED_CONVERSATION_ENGINE_V1.5.md)
- [`Citation integrity guard`](ai/CITATION_INTEGRITY_GUARD_V1.5.md)
- [`Commercial unified work area`](ux/V1.5_COMMERCIAL_AI_WORK_AREA.md)
- [`v1.5 acceptance criteria`](requirements/V1.5_ACCEPTANCE_CRITERIA.md)
- [`Static validation evidence`](testing/V1.5_STATIC_VALIDATION_EVIDENCE.md)
- [`Release validation report`](testing/V1.5_RELEASE_VALIDATION_REPORT.md)
- [`Release checksums`](testing/V1.5_RELEASE_CHECKSUMS.sha256)
- [`Owner-machine validation`](operations/V1.5_OWNER_MACHINE_VALIDATION.md)
- [`ADR-009`](architecture/adr/ADR-009-unified-conversation-and-citation-integrity.md)
- [`v1.5 PlantUML diagrams`](architecture/uml/v1.5/README.md)

## v1.6 ingestion and retrieval

- [`docs/implementation/PHASE_5_V1.6_IMPLEMENTATION_REPORT.md`](implementation/PHASE_5_V1.6_IMPLEMENTATION_REPORT.md)
- [`docs/data/V1.6_DOCUMENT_INGESTION_AND_RETRIEVAL.md`](data/V1.6_DOCUMENT_INGESTION_AND_RETRIEVAL.md)
- [`docs/api/V1.6_INGESTION_RETRIEVAL_API.md`](api/V1.6_INGESTION_RETRIEVAL_API.md)
- [`docs/ux/V1.6_CONTEXTUAL_UPLOAD_AND_ATTACHMENTS.md`](ux/V1.6_CONTEXTUAL_UPLOAD_AND_ATTACHMENTS.md)
- [`docs/requirements/V1.6_ACCEPTANCE_CRITERIA.md`](requirements/V1.6_ACCEPTANCE_CRITERIA.md)
- [`docs/operations/V1.6_OWNER_MACHINE_VALIDATION.md`](operations/V1.6_OWNER_MACHINE_VALIDATION.md)
- [`docs/architecture/adr/ADR-010-authorised-versioned-ingestion-and-retrieval.md`](architecture/adr/ADR-010-authorised-versioned-ingestion-and-retrieval.md)
- [`docs/architecture/uml/v1.6/README.md`](architecture/uml/v1.6/README.md)
- [`docs/testing/V1.6_STATIC_VALIDATION_EVIDENCE.md`](testing/V1.6_STATIC_VALIDATION_EVIDENCE.md)
- [`docs/testing/V1.6_RELEASE_VALIDATION_REPORT.md`](testing/V1.6_RELEASE_VALIDATION_REPORT.md)


## v1.7 teaching-output production

- [`docs/implementation/PHASE_6_V1.7_IMPLEMENTATION_REPORT.md`](implementation/PHASE_6_V1.7_IMPLEMENTATION_REPORT.md)
- [`docs/api/V1.7_TEACHING_OUTPUT_API.md`](api/V1.7_TEACHING_OUTPUT_API.md)
- [`docs/ai/V1.7_TEACHING_OUTPUT_PRODUCTION.md`](ai/V1.7_TEACHING_OUTPUT_PRODUCTION.md)
- [`docs/security/V1.7_ASSESSMENT_SAFETY.md`](security/V1.7_ASSESSMENT_SAFETY.md)
- [`docs/ux/V1.7_INLINE_EDIT_VERSION_EXPORT.md`](ux/V1.7_INLINE_EDIT_VERSION_EXPORT.md)
- [`docs/requirements/V1.7_ACCEPTANCE_CRITERIA.md`](requirements/V1.7_ACCEPTANCE_CRITERIA.md)
- [`docs/operations/V1.7_OWNER_MACHINE_VALIDATION.md`](operations/V1.7_OWNER_MACHINE_VALIDATION.md)
- [`docs/testing/V1.7_STATIC_VALIDATION_EVIDENCE.md`](testing/V1.7_STATIC_VALIDATION_EVIDENCE.md)
- [`docs/testing/V1.7_RELEASE_VALIDATION_REPORT.md`](testing/V1.7_RELEASE_VALIDATION_REPORT.md)
- [`docs/architecture/adr/ADR-011-inline-output-lifecycle-and-assessment-safety.md`](architecture/adr/ADR-011-inline-output-lifecycle-and-assessment-safety.md)
- [`docs/architecture/uml/v1.7/README.md`](architecture/uml/v1.7/README.md)
- [`packages/artifact-schemas/README.md`](../packages/artifact-schemas/README.md)


## v1.8 moderation and external review

- [`Phase 7 implementation report`](implementation/PHASE_7_V1.8_IMPLEMENTATION_REPORT.md)
- [`Moderation and review API`](api/V1.8_MODERATION_REVIEW_API.md)
- [`External review access security`](security/V1.8_EXTERNAL_REVIEW_ACCESS.md)
- [`Inline review workflow UX`](ux/V1.8_INLINE_REVIEW_WORKFLOW.md)
- [`v1.8 acceptance criteria`](requirements/V1.8_ACCEPTANCE_CRITERIA.md)
- [`Owner-machine validation`](operations/V1.8_OWNER_MACHINE_VALIDATION.md)
- [`ADR-012`](architecture/adr/ADR-012-assignment-specific-review-and-sealed-packs.md)
- [`v1.8 PlantUML diagrams`](architecture/uml/v1.8/README.md)
- [`Static validation evidence`](testing/V1.8_STATIC_VALIDATION_EVIDENCE.md)
- [`Release validation report`](testing/V1.8_RELEASE_VALIDATION_REPORT.md)
- [`Release checksums`](testing/V1.8_RELEASE_CHECKSUMS.sha256)


## v1.9 departmental teaching operations

- [`Phase 8 implementation report`](implementation/PHASE_8_V1.9_IMPLEMENTATION_REPORT.md)
- [`Department operations API`](api/V1.9_DEPARTMENT_OPERATIONS_API.md)
- [`Operational scope security`](security/V1.9_OPERATIONAL_SCOPE_SECURITY.md)
- [`Unified operations UX`](ux/V1.9_DEPARTMENT_OPERATIONS_UX.md)
- [`v1.9 acceptance criteria`](requirements/V1.9_ACCEPTANCE_CRITERIA.md)
- [`Owner-machine validation`](operations/V1.9_OWNER_MACHINE_VALIDATION.md)
- [`ADR-013`](architecture/adr/ADR-013-DEPARTMENTAL-TEACHING-OPERATIONS.md)
- [`v1.9 PlantUML diagrams`](architecture/uml/v1.9/README.md)
- [`Static validation evidence`](testing/V1.9_STATIC_VALIDATION_EVIDENCE.md)
- [`Release validation report`](testing/V1.9_RELEASE_VALIDATION_REPORT.md)
- [`Release checksums`](testing/V1.9_RELEASE_CHECKSUMS.sha256)


## v2.0 consolidated validation readiness

- [`Validation status`](../VALIDATION_STATUS.md)
- [`Phase 9 implementation report`](implementation/PHASE_9_V2.0_VALIDATION_READINESS_IMPLEMENTATION_REPORT.md)
- [`Consolidated owner-machine procedure`](operations/V2.0_CONSOLIDATED_OWNER_MACHINE_VALIDATION.md)
- [`Runtime validation matrix`](testing/V2.0_RUNTIME_VALIDATION_MATRIX.md)
- [`Failure triage and rollback`](testing/V2.0_FAILURE_TRIAGE_AND_ROLLBACK.md)
- [`v2.0 acceptance criteria`](requirements/V2.0_ACCEPTANCE_CRITERIA.md)
- [`Static validation evidence`](testing/V2.0_STATIC_VALIDATION_EVIDENCE.md)
- [`Release validation report`](testing/V2.0_RELEASE_VALIDATION_REPORT.md)
- [`Release checksums`](testing/V2.0_RELEASE_CHECKSUMS.sha256)
- [`ADR-014`](architecture/adr/ADR-014-consolidated-owner-machine-validation-gate.md)
- [`v2.0 PlantUML diagrams`](architecture/uml/v2.0/README.md)


## v2.1 commercial unified workspace

- [`Phase 10 implementation report`](implementation/PHASE_10_V2.1_COMMERCIAL_WORKSPACE_IMPLEMENTATION_REPORT.md)
- [`Commercial workspace API`](api/V2.1_COMMERCIAL_WORKSPACE_API.md)
- [`Commercial unified workspace UX`](ux/V2.1_COMMERCIAL_UNIFIED_WORKSPACE.md)
- [`Search and personal workspace security`](security/V2.1_SEARCH_AND_PERSONAL_WORKSPACE_SECURITY.md)
- [`v2.1 acceptance criteria`](requirements/V2.1_ACCEPTANCE_CRITERIA.md)
- [`Owner-machine validation`](operations/V2.1_OWNER_MACHINE_VALIDATION.md)
- [`Static validation evidence`](testing/V2.1_STATIC_VALIDATION_EVIDENCE.md)
- [`Release validation report`](testing/V2.1_RELEASE_VALIDATION_REPORT.md)
- [`ADR-015`](architecture/adr/ADR-015-commercial-unified-workspace-and-authorised-search.md)
- [`v2.1 PlantUML diagrams`](architecture/uml/v2.1/README.md)

## v2.2 scoped analytics and commercial governance

- [`Phase 11 implementation report`](implementation/PHASE_11_V2.2_ANALYTICS_GOVERNANCE_IMPLEMENTATION_REPORT.md)
- [`Analytics, reporting and governance API`](api/V2.2_ANALYTICS_REPORTING_GOVERNANCE_API.md)
- [`Insights, reports, Audit Centre and settings UX`](ux/V2.2_INSIGHTS_REPORTS_AUDIT_SETTINGS.md)
- [`Analytics, audit and settings security`](security/V2.2_ANALYTICS_AUDIT_AND_SETTINGS_SECURITY.md)
- [`AI usage governance`](governance/AI_USAGE_GOVERNANCE.md)
- [`Analytics data model`](data/V2.2_ANALYTICS_DATA_MODEL.md)
- [`v2.2 acceptance criteria`](requirements/V2.2_ACCEPTANCE_CRITERIA.md)
- [`Owner-machine validation`](operations/V2.2_OWNER_MACHINE_VALIDATION.md)
- [`Static validation evidence`](testing/V2.2_STATIC_VALIDATION_EVIDENCE.md)
- [`Release validation report`](testing/V2.2_RELEASE_VALIDATION_REPORT.md)
- [`ADR-016`](architecture/adr/ADR-016-scoped-analytics-ai-governance-and-audit-centre.md)
- [`v2.2 PlantUML diagrams`](architecture/uml/v2.2/README.md)

## v2.3 production hardening and operational readiness

- [`Phase 12 implementation report`](implementation/PHASE_12_V2.3_PRODUCTION_HARDENING_IMPLEMENTATION_REPORT.md)
- [`Operations and reliability API`](api/V2.3_OPERATIONS_AND_RELIABILITY_API.md)
- [`Production security hardening`](security/V2.3_PRODUCTION_HARDENING.md)
- [`Background jobs and workers`](operations/V2.3_BACKGROUND_JOBS_AND_WORKERS.md)
- [`Backup, restore and disaster recovery`](operations/V2.3_BACKUP_RESTORE_AND_DR.md)
- [`Deployment and observability`](operations/V2.3_DEPLOYMENT_AND_OBSERVABILITY.md)
- [`Owner-machine validation`](operations/V2.3_OWNER_MACHINE_VALIDATION.md)
- [`Synthetic corpus and onboarding pack`](data/V2.3_SYNTHETIC_CORPUS_AND_ONBOARDING_PACK.md)
- [`v2.3 acceptance criteria`](requirements/V2.3_ACCEPTANCE_CRITERIA.md)
- [`Static validation evidence`](testing/V2.3_STATIC_VALIDATION_EVIDENCE.md)
- [`Release validation report`](testing/V2.3_RELEASE_VALIDATION_REPORT.md)
- [`ADR-017`](architecture/adr/ADR-017-durable-jobs-and-production-hardening.md)
- [`v2.3 PlantUML diagrams`](architecture/uml/v2.3/README.md)


## v2.4 durable domain automation

- [`Phase 13 implementation report`](implementation/PHASE_13_V2.4_DOMAIN_AUTOMATION_IMPLEMENTATION_REPORT.md)
- [`Automation and operations API`](api/V2.4_AUTOMATION_AND_OPERATIONS_API.md)
- [`Background domain execution`](operations/V2.4_BACKGROUND_DOMAIN_EXECUTION.md)
- [`Retention and delivery safety`](security/V2.4_RETENTION_AND_DELIVERY_SAFETY.md)
- [`Platform operations UX`](ux/V2.4_PLATFORM_OPERATIONS_EXPERIENCE.md)
- [`v2.4 acceptance criteria`](requirements/V2.4_ACCEPTANCE_CRITERIA.md)
- [`Owner-machine validation`](operations/V2.4_OWNER_MACHINE_VALIDATION.md)
- [`Static validation evidence`](testing/V2.4_STATIC_VALIDATION_EVIDENCE.md)
- [`Release validation report`](testing/V2.4_RELEASE_VALIDATION_REPORT.md)
- [`Release checksums`](testing/V2.4_RELEASE_CHECKSUMS.sha256)
- [`ADR-018`](architecture/adr/ADR-018-durable-domain-automation.md)
- [`v2.4 PlantUML diagrams`](architecture/uml/v2.4/README.md)


## v2.5 completion gap closure and commercial release preparation

- [`Phase 14 implementation report`](implementation/PHASE_14_V2.5_COMPLETION_GAP_CLOSURE_IMPLEMENTATION_REPORT.md)
- [`Completion, enterprise and commercial API`](api/V2.5_COMPLETION_ENTERPRISE_COMMERCIAL_API.md)
- [`Account recovery, MFA and SSO`](security/ACCOUNT_RECOVERY_MFA_AND_SSO_V2.5.md)
- [`Enterprise integration framework`](integrations/ENTERPRISE_INTEGRATION_FRAMEWORK_V2.5.md)
- [`Real-data preparation and rights gate`](data/REAL_DATA_PREPARATION_AND_RIGHTS_GATE_V2.5.md)
- [`Pilot evaluation and feedback`](research/PILOT_EVALUATION_AND_FEEDBACK_V2.5.md)
- [`Commercial release readiness`](product/V2.5_COMMERCIAL_RELEASE_READINESS.md)
- [`Commercial pilot plan`](pilot/COMMERCIAL_PILOT_PLAN_V2.5.md)
- [`v2.5 acceptance criteria`](requirements/V2.5_ACCEPTANCE_CRITERIA.md)
- [`Owner-machine validation`](operations/V2.5_OWNER_MACHINE_VALIDATION.md)
- [`Static validation evidence`](testing/V2.5_STATIC_VALIDATION_EVIDENCE.md)
- [`Release validation report`](testing/V2.5_RELEASE_VALIDATION_REPORT.md)
- [`ADR-019`](architecture/adr/ADR-019-completion-gap-closure-and-enterprise-boundaries.md)
- [`v2.5 PlantUML diagrams`](architecture/uml/v2.5/README.md)
- [`Legal templates`](legal/TERMS_OF_SERVICE_TEMPLATE.md)

## v2.6 deployment completion

- [`../PUSH_AND_DEPLOY.md`](../PUSH_AND_DEPLOY.md)
- [`../RELEASE_NOTES_v2.6.0.md`](../RELEASE_NOTES_v2.6.0.md)
- [`../DEPLOYMENT_QUICKSTART.md`](../DEPLOYMENT_QUICKSTART.md)
- [`operations/VERCEL_RENDER_NEON_DEPLOYMENT.md`](operations/VERCEL_RENDER_NEON_DEPLOYMENT.md)
- [`operations/DEPLOYMENT_PARITY_RUNBOOK.md`](operations/DEPLOYMENT_PARITY_RUNBOOK.md)
- [`security/GITHUB_AND_DEPLOYMENT_SECURITY.md`](security/GITHUB_AND_DEPLOYMENT_SECURITY.md)
- [`requirements/V2.6_ACCEPTANCE_CRITERIA.md`](requirements/V2.6_ACCEPTANCE_CRITERIA.md)
- [`testing/V2.6_STATIC_VALIDATION_EVIDENCE.md`](testing/V2.6_STATIC_VALIDATION_EVIDENCE.md)
- [`testing/V2.6_RELEASE_VALIDATION_REPORT.md`](testing/V2.6_RELEASE_VALIDATION_REPORT.md)
- [`architecture/adr/ADR-020-deployment-parity-and-managed-platform-topology.md`](architecture/adr/ADR-020-deployment-parity-and-managed-platform-topology.md)
- [`architecture/uml/v2.6/README.md`](architecture/uml/v2.6/README.md)
- [`releases/V2.6_DEPLOYMENT_READY_RELEASE.md`](releases/V2.6_DEPLOYMENT_READY_RELEASE.md)
