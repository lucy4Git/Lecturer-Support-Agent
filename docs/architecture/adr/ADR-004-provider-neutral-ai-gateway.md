# ADR-004: Provider-Neutral AI Gateway

**Status:** Accepted

## Decision

All model calls pass through an internal gateway. Initial adapters support OpenAI, Anthropic Claude, Google Gemini, DeepSeek API and local Ollama models. Ordinary users do not select models or providers.

Cloud model IDs are discovered through official provider model endpoints and mapped to stable internal capability aliases. Local models are maintained in a governed registry and installed through controlled scripts.

## Consequences

Routing, fallback, privacy, source integrity, cost, health and evaluation are centrally governed. The platform avoids a single-provider dependency but must maintain provider adapters, policy metadata, evaluation coverage and auditable routing.

A fallback may never weaken tenant isolation or data-handling requirements.
