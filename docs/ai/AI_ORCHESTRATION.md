# AI Orchestration

Pipeline: parse conversation and attachments; resolve tenant, roles and scope; classify intent, discipline, level, modality, sensitivity and risk; decide whether external, institutional, user or no retrieval is needed; build a capability requirement; select an approved provider/model through the multi-provider gateway; generate a structured draft; validate facts, sources, policy claims, safety, academic integrity and schema; stream the readable response or inline artifact; persist output version, provider/model, routing decision, fallbacks, sources, execution, cost and audit; offer authorised next actions.

Initial provider adapters cover OpenAI, Anthropic Claude, Google Gemini, DeepSeek API and local Ollama models. Ordinary users do not select providers or models. Cloud model IDs are discovered and approved through the registry; application code uses stable internal aliases.

The orchestrator never grants access. Authorization is resolved before any content, retrieval, provider call or tool use. A fallback may not weaken privacy, tenant isolation or data-class controls. Source verification remains independent of whichever model generated the draft.
