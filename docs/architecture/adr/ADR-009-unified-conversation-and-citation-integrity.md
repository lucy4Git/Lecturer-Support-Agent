# ADR-009: Provider-Neutral Unified Conversation and Citation Integrity

- **Status:** Accepted for v1.5; runtime validation pending
- **Date:** 24 July 2026

## Context

The product requires generic ChatGPT-style assistance, multiple cloud and local providers, genuine sources, no model picker, and one inline work area. A retrieval-only design would fail the generic-assistance requirement, while allowing models to construct references would violate source integrity.

## Decision

1. Use one conversation engine and provider contract.
2. Classify task, privacy, source need, and review need before generation.
3. Use capability/privacy fallback routing; ordinary users do not select models.
4. Keep institutional context optional.
5. Retrieve sources before generation and number them.
6. Allow citations only to actual retrieval records from the same AI request.
7. Remove unknown citations, links, and DOIs after generation.
8. Render the result and source cards inline.
9. Preserve provider attempts, output versions, source retrievals, citations, and audit evidence.

## Consequences

- Provider-specific behaviour is isolated in adapters.
- Local routing can protect restricted data.
- Source cards are traceable but claim-level verification remains a later evaluation layer.
- Crossref improves scholarly source metadata but is not a general web-search solution.
- Streaming and rich attachment context can be added without changing the conversation contract.
