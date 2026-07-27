# AI Configuration

These files define the provider-neutral AI gateway without storing API keys.

- `providers.example.json`: OpenAI, Anthropic Claude, Google Gemini, DeepSeek and Ollama adapters.
- `model-registry.example.json`: stable routing aliases and candidate model records.
- `ollama-model-profiles.json`: minimal, standard and advanced local pull profiles.

Cloud model IDs remain environment/admin configuration because provider catalogues and lifecycle stages change. Production promotion requires evaluation and approval.
