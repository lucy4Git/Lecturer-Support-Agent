# Requirements Traceability Matrix

| Requirement group | Design | PlantUML | Primary tests |
|---|---|---|---|
| FR-001–005 | `docs/ux/UNIFIED_AI_WORK_AREA.md` | `sequences/01_unified_prompt_to_artifact.plantuml` | `tests/e2e/unified-work-area/` |
| FR-010–014 | `docs/ai/TEACHING_AND_ASSESSMENT_GENERATION.md` | lesson/assessment sequences | `tests/ai-evaluation/pedagogy/` |
| FR-020–025 | `docs/ai/SOURCE_VERIFICATION_AND_CITATIONS.md` | source verification sequence | `tests/ai-evaluation/citations/` |
| FR-030–033 | multi-tenancy design | ERD | `tests/security/tenant-isolation/` |
| FR-040–046 | role matrix | use-case/role diagrams | `tests/security/authorization/` |
| FR-050–057 | ingestion/versioning docs | bulk sequence/activity/version state | `tests/integration/bulk-ingestion/` |
| FR-060–062 | moderation/external review | moderation/external sequences | `tests/e2e/moderation/` |
| FR-070–073 | export/audit services | component/export diagrams | integration/E2E |

| v2.1 unified commercial navigation | `docs/ux/V2.1_COMMERCIAL_UNIFIED_WORKSPACE.md` | `docs/architecture/uml/v2.1/commercial_unified_workspace_components.puml` | `tests/e2e/live-preview/commercial-workspace.spec.ts` |
| v2.1 authorised cross-resource search | `docs/security/V2.1_SEARCH_AND_PERSONAL_WORKSPACE_SECURITY.md` | `docs/architecture/uml/v2.1/authorised_search_sequence.puml` | `tests/unit/test_v21_commercial_workspace.py` |
| v2.1 Library and Files attachment | `docs/api/V2.1_COMMERCIAL_WORKSPACE_API.md` | `docs/architecture/uml/v2.1/library_attach_sequence.puml` | `tests/e2e/live-preview/commercial-workspace.spec.ts` |
| v2.1 exact-version saved outputs | `docs/api/V2.1_COMMERCIAL_WORKSPACE_API.md` | `docs/architecture/uml/v2.1/saved_output_sequence.puml` | `tests/unit/test_v21_commercial_workspace.py` |
| v2.1 actionable notifications | `docs/implementation/PHASE_10_V2.1_COMMERCIAL_WORKSPACE_IMPLEMENTATION_REPORT.md` | `docs/architecture/uml/v2.1/notification_sequence.puml` | `tests/unit/test_v21_commercial_workspace.py` |
