# Multi-Provider Model Strategy

## Decision

The Lecturer Support Agent is **provider-neutral and multi-model**. OpenAI is one supported provider, not the sole provider. Initial adapters cover:

- OpenAI;
- Anthropic Claude;
- Google Gemini;
- DeepSeek API;
- Ollama-hosted local models.

Future adapters may add institution-approved managed or self-hosted providers without changing the unified user experience.

## Why

A single-provider dependency creates avoidable risks: outage exposure, vendor lock-in, price changes, model retirement, data-jurisdiction constraints, uneven capability coverage and weak offline resilience. Multiple providers allow the platform to choose the best approved capability while preserving governance.

## User experience

Ordinary users do not choose a provider or model. They use one ChatGPT-style work area. The orchestration gateway chooses an approved model based on task, data class, discipline, modality, quality, latency, cost, availability and institutional policy. Administrators govern provider eligibility; technical operators maintain credentials and deployments.

## Provider roles

| Provider | Intended initial role | Important boundary |
|---|---|---|
| OpenAI | General generation, reasoning, tools and multimodal tasks | Cloud processing only when the tenant and data class permit it |
| Anthropic Claude | Long-form drafting, analysis, reasoning and tool workflows | Cloud processing only when contract and data policy permit it |
| Google Gemini | Multimodal, audio/video and broad teaching-content workflows | Model availability must be discovered and lifecycle reviewed |
| DeepSeek API | Reasoning and cost-sensitive text workloads | Use the official API adapter and apply the same data controls as every cloud provider |
| Ollama | Local/offline inference, private development, resilience and local-model evaluation | Local does not automatically mean approved; host security, licensing and quality still apply |

## No hard-coded cloud model IDs

Cloud model catalogues change. The gateway discovers models through official provider endpoints and maps administrator-approved model IDs to stable internal aliases such as `general-balanced`, `reasoning-high` and `multimodal-teaching`. Application code uses aliases, not rapidly changing provider names.

## Required controls

Every request records the provider, model, model version where available, prompt/template version, routing decision, data-class decision, tools, sources, token usage, latency, validation results and fallback history. Secrets never enter source control or client-side code.

## Source integrity

Model diversity does not replace source verification. A response may be generic, but every displayed citation must come from a genuinely retrieved source record. No provider is trusted to invent a reference, DOI, URL, institutional policy or compliance claim.

## Local models

The initial Ollama profiles include Qwen, DeepSeek-R1 distilled models, Gemma and multilingual embedding models. They are candidates for benchmarking, not automatic production approvals. Each must pass licensing, privacy, security, quality, bias, hallucination, citation and performance gates.
