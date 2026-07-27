# Model Routing and Fallback

## Routing sequence

1. Resolve tenant, user, roles and organisational scope.
2. Classify the request by task, discipline, qualification level, modality, sensitivity and risk.
3. Determine whether the request may leave the institution-controlled environment.
4. Build a capability requirement: text, vision, audio/video, tools, structured output, long context, reasoning or embeddings.
5. Filter the registry to enabled, healthy, approved models that meet the data-class policy.
6. Rank candidates by evaluation quality, latency, cost, availability and tenant preference.
7. Execute through the provider adapter.
8. Validate structure, safety, source integrity, academic level and factual claims.
9. Retry or fall back only within an equivalent or stronger privacy policy.
10. Persist the complete routing and validation record.

## Hard rules

- Confidential or restricted content must never fall back from an approved local/self-hosted route to an unapproved cloud route.
- A provider outage must produce a transparent degraded response or safe refusal rather than weaken policy.
- External reviewers remain limited to assigned content regardless of provider.
- Source retrieval and citation verification are independent of the generation model.
- High-stakes assessments require human review even when multiple models agree.

## Fallback classes

- **Equivalent cloud fallback:** another approved cloud model with equal data-processing terms and required capabilities.
- **Local fallback:** an approved Ollama model when local quality is sufficient.
- **Reduced-capability fallback:** only for non-critical tasks, clearly marked, with validation.
- **No fallback:** restricted content, unsupported modality, failed source verification or missing approval.

## Ensemble use

Multiple models may be used for high-risk generation, rubric checking, contradiction detection or citation review. Ensemble use must be justified because it increases cost, latency and data exposure. Models must not see content beyond their approved data class.

## Evaluation

Routing decisions are evaluated by task success, hallucination, fabricated-citation rate, pedagogical quality, data-policy compliance, latency, cost and fallback correctness. Model preference is evidence-based, not brand-based.
