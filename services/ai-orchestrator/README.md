# AI Orchestrator

The importable v1.5 implementation currently lives under `services/api/app/ai/` and provides:

- explainable teaching-task and privacy classification;
- prompt and verified-source-pack construction;
- provider-neutral OpenAI, Anthropic, Gemini, DeepSeek, Ollama, and development-mock adapters;
- privacy-aware fallback routing;
- Crossref scholarly metadata discovery;
- citation marker, URL, and DOI integrity checks;
- provider attempt and source provenance contracts.

A later service extraction may move this into its own deployable process without changing the contracts. Implementation must follow `PROJECT_CONSTITUTION.md`, ADR-009, requirements, and security rules.
