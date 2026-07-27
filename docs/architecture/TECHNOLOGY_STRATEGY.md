# Technology Strategy

Reference stack, subject to ADR approval:

- Web/PWA: Next.js, React, TypeScript and accessible component primitives.
- Backend/AI: FastAPI/Python with versioned OpenAPI contracts.
- Data: PostgreSQL, Redis, S3-compatible object storage, full-text search and vector database.
- Jobs/events: durable queue/broker with retries, idempotency and dead letters.
- AI: provider-neutral gateway with initial OpenAI, Anthropic Claude, Google Gemini, DeepSeek and Ollama adapters; capability-based routing; dynamic cloud-model discovery; governed local model profiles; no ordinary-user model selector.
- Sources: provider-independent retrieval, verification and citation records; generation models cannot self-authorise citations.
- Observability: OpenTelemetry, structured logs, metrics, traces and alerts, including provider/model/fallback telemetry without excessive sensitive-content logging.
- Infrastructure: explicit Docker Compose startup for local work; production orchestration/IaC based on scale and operating capability.

Technology follows requirements, security, maintainability, portability, skills and total cost rather than novelty.
