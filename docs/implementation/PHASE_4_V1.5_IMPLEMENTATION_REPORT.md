# Phase 4 — v1.5 Unified AI Conversation Engine Implementation Report

## Status

**Implemented in code; owner-machine runtime, live-provider, database, and browser validation pending.**

## Purpose

v1.5 turns the v1.4 role-aware shell into the first functional unified Lecturer Support Agent work area. A user submits any authorised teaching-and-learning request in one conversation, the platform classifies the task, applies privacy-aware provider routing, generates an inline output, validates references against sources actually retrieved, persists the conversation and model execution, and returns source cards without creating a separate artifact workspace.

## Implemented capabilities

1. **Unified conversation API** for creating, listing, opening, archiving, and continuing conversations.
2. **Teaching-task classification** for lesson plans, practical lessons, quizzes, tests, assignments, examinations, rubrics, marking guides, case studies, tutorials, moderation, alignment, departmental analysis, and generic teaching questions.
3. **Provider-neutral adapters** for OpenAI, Anthropic Claude, Google Gemini, DeepSeek, Ollama, and a deterministic development mock.
4. **Privacy-aware routing and fallback**. Confidential and restricted-assessment requests are local-only when `AI_REQUIRE_LOCAL_FOR_RESTRICTED=true`.
5. **Generic-by-default response behaviour**. Institutional material is optional context, not a mandatory grounding dependency.
6. **Crossref scholarly metadata discovery** when a request materially calls for sources.
7. **Citation integrity guard** that accepts only source markers, URLs, and DOIs present in the actual retrieved source pack.
8. **Inline output persistence** using the existing conversation, AI request, model execution, generated output, output version, source retrieval, citation, verification, audit, and outbox records.
9. **Commercial conversation UI foundation** with recent conversations, inline assistant output, provider/model disclosure, source cards, integrity warnings, human-review notices, mobile navigation, and contextual role actions.
10. **Deterministic unit tests** for classification, routing, provider adapters, Crossref parsing, prompt constraints, and citation sanitisation.

## Important design decisions

- No user-facing model picker was introduced.
- No separate artifact workspace was introduced.
- Provider keys remain environment secrets and are never persisted in source control or the database.
- A retrieved source card confirms genuine metadata retrieval; it does not automatically prove every generated claim.
- Formal examinations, moderation outputs, and alignment reviews are always marked for authorised human review.
- The development mock is permitted only outside production and never fabricates sources.

## Files introduced

- `services/api/app/ai/`
- `services/api/app/schemas/conversations.py`
- `services/api/app/services/conversation_engine.py`
- `services/api/app/routes/conversations.py`
- `tests/unit/test_v15_ai_conversation.py`
- v1.5 API, AI, UX, testing, operations, requirements, ADR, and UML documentation

## Validation completed in this build environment

- Python compilation passed.
- 30 unit tests passed.
- FastAPI application loaded with the v1.5 conversation routes.
- TypeScript and TSX syntax validation passed.
- Citation integrity tests passed.
- Provider adapter payload and parsing tests passed using mocked HTTP transports.
- No real API key, `.env`, provider secret, model binary, institutional data, or student data was added.

## Owner-machine validation still required

- PostgreSQL migration and RLS execution inherited from v1.3/v1.4.
- Authenticated conversation persistence using seeded users.
- Live Ollama generation.
- Live OpenAI, Anthropic, Gemini, and DeepSeek calls for configured providers.
- Crossref network retrieval.
- Provider fallback under real timeout and rate-limit conditions.
- Next.js dependency installation, typecheck, production build, and browser preview.
- Desktop, tablet, mobile, accessibility, failure-state, and multi-role live testing.
- Source-card links and citation records against the live database.

## Next planned checkpoint

v1.6 should extend the conversation engine with evaluated prompt/output contracts for each teaching task, attachment-aware institutional context retrieval, streaming responses, output revision actions, and richer claim-level citation verification. It should not begin before the consolidated owner-machine validation identifies and corrects v1.3–v1.5 runtime defects.
