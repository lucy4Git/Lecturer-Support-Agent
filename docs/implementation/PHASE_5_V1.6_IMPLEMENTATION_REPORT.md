# Phase 5 implementation report — v1.6

## Implemented

- Five new tenant-owned data tables for ingestion jobs, extracted contents, chunks, version transitions, and institutional retrieval traces.
- Alembic migration `20260725_0003` with application-role grants and RLS reapplication.
- Safe ZIP inspection and expansion with traversal, link, encryption, nesting, entry-count and expansion limits.
- Text extraction for common teaching formats; transcript-required handling for audio/video and fail-honest image handling.
- Deterministic paragraph-aware chunking, governed Ollama embedding adapter, Qdrant collection validation, version replacement and scoped search.
- Defence-in-depth document access service and source-aware institutional retrieval tied to the active tenant, role, scope, document version, and AI request.
- Contextual multi-file/ZIP upload interface in the unified work area; successful versions become removable message attachments.
- Institutional source-card metadata and prompt excerpts without compulsory grounding for generic requests.
- Controlled document lifecycle transition service and API with review/approval permissions and append-only transition records.
- Defence-in-depth owner and target-scope checks inside document version creation, plus access-filtered document listing and history.
- Tests, validation scripts, PlantUML, ADR-010, API/data/UX/acceptance documentation.

## Why

The system must support daily teaching work without losing version history or exposing one institution's content to another. The AI remains generic by default, but can use explicitly attached or contextually relevant authorised material when the user needs institutional alignment.

## Runtime status

**IMPLEMENTED — OWNER-MACHINE VALIDATION PENDING.** Live PostgreSQL migration, MinIO retrieval, Ollama embeddings, Qdrant indexing/search, large-file processing, Next.js build, browser preview, accessibility, performance and recovery tests have not been claimed as complete in this environment.


## Static checkpoint evidence

- 64 SQLAlchemy tables across 11 PostgreSQL schemas.
- 44 FastAPI routes and 37 OpenAPI paths.
- 56 editable PlantUML sources.
- 40 unit tests passed.
- All cumulative validators from the Data Foundation through v1.6 passed.
- TypeScript/TSX syntax validation passed.

These results do not replace owner-machine integration evidence.
