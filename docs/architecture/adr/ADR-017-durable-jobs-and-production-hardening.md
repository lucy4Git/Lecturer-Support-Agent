# ADR-017 — Durable Jobs and Production Hardening

## Status

Accepted for v2.3; runtime validation pending.

## Decision

Use PostgreSQL as the authoritative durable job ledger with lease-based `SKIP LOCKED` claiming, bounded exponential retry, dead letters, and tenant-scoped idempotency. Redis may support rate limiting and operational acceleration but is not the sole record of long-running academic work.

Uploads integrate with a local or institution-approved ClamAV service. Production settings fail closed when rate limiting, malware scanning, or metrics protection is unsafe. Liveness and readiness are separate. Logs and metrics must not expose prompts, documents, student data, or credentials.

## Consequences

The design is recoverable and auditable but requires live PostgreSQL, worker, scanner, and backup testing. Domain handlers remain incomplete until explicitly wired and validated; the framework must not disguise this status.
