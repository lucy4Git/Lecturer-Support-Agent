# Phase 13 — v2.4 Durable Domain Automation

## Purpose

v2.3 established a durable queue but deliberately left domain handlers disconnected. v2.4 connects the jobs that can be implemented safely before owner-machine validation while preserving fail-closed behaviour for infrastructure-specific backup and restore operations.

## Implemented

- Durable in-app notification delivery evidence and visible blocking for unconfigured outbound channels.
- Internal outbox publication with idempotent published timestamps.
- Time-based external-access expiry, expiry-event processing, audit evidence, and user notification.
- Governed retention runs with preview mode, per-resource evidence, and only reversible archive/expiry actions.
- Worker execution for analytics reports and audit exports with SHA-256 integrity values.
- Worker integration contracts for document ingestion and teaching-output export using MinIO/S3, Ollama embeddings, and Qdrant.
- Governed interval schedules materialised by a restricted PostgreSQL `SECURITY DEFINER` function.
- Institution Administrator APIs and unified-interface operations panel for schedules, jobs, retention and delivery evidence.
- Automatic queuing for notification dispatch, audit outbox publication and external-access expiry.

## Deliberate boundaries

`operations.backup` and `operations.restore_drill` still raise a clear `NotImplementedError` until a real destination and restore environment are configured and validated. Cron expressions, email, SMS and webhooks are not presented as operational. Hard deletion is not supported by the retention worker.

## Status

**IMPLEMENTED — STATICALLY VALIDATED — OWNER-MACHINE VALIDATION PENDING**
