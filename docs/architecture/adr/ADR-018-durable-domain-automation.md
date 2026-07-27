# ADR-018: Durable Domain Automation

- **Status:** Accepted
- **Date:** 2026-07-26

## Decision

Connect the durable PostgreSQL queue to allow-listed domain handlers, use interval schedules materialised by a restricted `SECURITY DEFINER` function, retain row-level security for the worker, and implement retention as preview-first and reversible-only.

## Rationale

Long-running ingestion, exports, reports, expiry and delivery work must survive web-request termination. At the same time, background execution must not bypass tenant isolation or falsely report unconfigured external services as successful.

## Consequences

- Real in-app delivery is auditable.
- Unsupported outbound channels fail visibly.
- External access can expire without a user request.
- Report, audit, ingestion and export work can execute durably.
- Hard deletion and unconfigured backup destinations remain out of scope until formally approved and runtime validated.
