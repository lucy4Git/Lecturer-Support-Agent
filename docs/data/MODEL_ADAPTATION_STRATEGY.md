# Model Adaptation Strategy

## 1. Position

The Lecturer Support Agent will not train a foundation model from scratch. It uses a provider-neutral model fabric with OpenAI, Anthropic Claude, Google Gemini, DeepSeek API and approved Ollama-hosted local models. No single provider is mandatory for every task. Production routing remains governed by institutional privacy, data class, capability, quality, availability, latency and cost.

## 2. Adaptation ladder

Use the least invasive method that achieves the required quality:

1. clear system and task instructions;
2. structured output schemas and validation;
3. tools for calculations, document generation and source verification;
4. runtime context from user input and permitted institutional materials;
5. retrieval for current, authoritative or institution-specific evidence;
6. prompt examples selected by task, discipline and qualification level;
7. routing/classification models for intent, risk and output type;
8. provider or local fine-tuning only after a formal gate;
9. no foundation pretraining within the initial programme.

## 3. Provider and local-model evaluation

Every provider/model candidate is evaluated separately. A brand-level approval is insufficient. The registry records provider, model ID, version/digest, deployment type, modalities, tools, context, data terms, approved data classes, benchmark results, cost/latency, lifecycle and retirement date.

Local Ollama models are candidates for offline development, resilience and privacy-sensitive routes. Local deployment does not remove licensing, security, hallucination, bias or quality requirements.

## 4. What fine-tuning may improve

Fine-tuning may be evaluated for stable behavioural tasks such as intent and artifact-type classification, consistent lesson-plan or rubric structure, discipline-aware tone and complexity, controlled academic taxonomy mapping, machine-readable metadata, safe refusal patterns and moderation finding classification.

Fine-tuning must not be the primary mechanism for current factual knowledge, changing institutional policies, live course assignments, source verification, permissions, confidential institutional knowledge or compliance determination. Those require retrieval, tools and authoritative system data.

## 5. Training candidate requirements

Any fine-tuning candidate must contain rights-cleared examples; explicit task, discipline, level, pedagogy and risk labels; no uncontrolled personal/confidential data; no evaluation overlap; expert review; negative and safe-refusal examples; a dataset card, provenance and version; reproducible splits; a rollback plan; and provider/local-runtime deletion capability where applicable.

## 6. Dataset split

Recommended starting split: training 70–80%, validation 10–15%, held-out test 10–15%, plus separate challenge and red-team sets. Split by source family to reduce near-duplicate leakage. Hold out entire modules, disciplines or institutions where possible.

## 7. Baseline experiment

Benchmark generic model without retrieval; structured prompting; verified-source tools; permitted institution retrieval; prompt examples; multiple cloud providers; multiple local candidates; and any fine-tuned candidate. Measure quality, source correctness, hallucination, safety, latency, cost, privacy, portability and maintainability.

## 8. Approval gate

Fine-tuning or production model promotion requires a defined gap and metric; lawful rights and privacy approval; representativeness review; independent held-out evaluation; safety and tenant-isolation tests; cost and lock-in assessment; model card; rollback; and project-owner approval.

## 9. Production feedback

User feedback may improve prompts and evaluations but does not automatically become training data. Training reuse requires explicit opt-in and a new review decision.

## 10. Continuous evaluation and routing

Every model, prompt, retrieval, source-verification or routing change receives a versioned evaluation. Release gates include task quality, fabricated-citation rate, supported-claim precision, unsafe instruction rate, tenant leakage, accessibility/bias, latency, cost and no high-risk regression.

Routing uses stable internal aliases and dynamic provider model discovery. Fallback is permitted only to an equivalent or stronger privacy/data policy.

## 11. Provider safeguards

Before sending content to any cloud provider, enforce tenant/model approval, data-class eligibility, redaction where required, minimum necessary context, contractual privacy settings, secret isolation, audited metadata and fallback rules that do not lower controls.
