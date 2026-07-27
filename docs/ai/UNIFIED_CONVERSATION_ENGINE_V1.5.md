# Unified Conversation Engine v1.5

## Objective

Provide one ChatGPT-style work area for every authorised lecturer-support task while keeping model choice, routing, source handling, persistence, and review controls invisible to ordinary users.

## Processing pipeline

1. Confirm active session, role assignment, tenant, and `ai.use` permission.
2. Persist the user message.
3. Classify task type, source need, institutional-context need, privacy class, entities, and human-review requirement.
4. Retrieve scholarly source metadata only when the request materially calls for evidence, sources, current research, policy, standards, or statistics.
5. Build a task-specific system prompt and a numbered verified source pack.
6. Route by privacy and configured provider order.
7. Fall back only to permitted providers.
8. Remove references not present in the verified source pack.
9. Persist model attempts, inline output version, source retrievals, citations, verification state, and audit evidence.
10. Return the output and source cards in the same conversation.

## Generic response principle

The agent is not retrieval-only. It can answer from the selected model's general capability when no institutional document or external source is required. When evidence is necessary but unavailable, it must say so rather than create a source.

## Task classifier

The deterministic classifier is the auditable first layer. It recognises:

- generic teaching answer;
- lesson and practical lesson;
- quiz, test, assignment, and examination;
- rubric and marking guide;
- case study and tutorial;
- moderation and alignment review;
- departmental analysis.

It also extracts duration, academic level, and mark allocation where explicit. An evaluated model-assisted classifier may later handle ambiguous requests, but the deterministic fallback must remain.

## Human-review controls

Examinations, moderation reviews, and alignment reviews are marked as requiring human review. The model may draft or analyse, but it cannot confer formal approval, moderation completion, policy compliance, or institutional authority.

## Provider support

Adapters implement provider-native HTTP contracts for:

- OpenAI Responses;
- Anthropic Messages;
- Gemini `generateContent`;
- DeepSeek chat completions;
- Ollama `/api/chat`;
- deterministic development mock.

Model identifiers are environment configuration, not hard-coded product decisions.
