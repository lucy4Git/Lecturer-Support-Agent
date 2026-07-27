# ADR-010: Authorised versioned ingestion and retrieval

**Status:** Accepted for v1.6  
**Decision:** Uploaded material remains immutable in object storage and PostgreSQL. Text extraction, chunking, embedding, and Qdrant indexing operate on a specific document-version identifier. Retrieval is tenant-filtered in Qdrant and re-authorised against PostgreSQL before any excerpt enters an AI prompt.

## Why

A user-facing filter alone is insufficient for a multi-institution platform. Version-aware indexing prevents a revised document from silently changing historical evidence, while defence-in-depth permission checks reduce cross-tenant and cross-scope exposure risk.

## Consequences

- Audio/video are preserved but require an authorised transcript before semantic indexing.
- Unsupported files are never assigned invented text.
- Superseded versions remain auditable but are excluded from default retrieval.
- The embedding dimension must match the Qdrant collection.
- Runtime integration remains owner-machine validation pending.
