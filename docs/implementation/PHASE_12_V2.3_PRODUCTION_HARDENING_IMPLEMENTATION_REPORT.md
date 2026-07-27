# Phase 12 — v2.3 Production Hardening and Operational Readiness

## Purpose

v2.3 implements the non-institution-specific work that can be completed before owner-machine and pilot validation: durable background processing, request hardening, malware-scanning integration, structured observability, real dependency readiness probes, backup/restore automation, production container definitions, Kubernetes foundations, CI gates, deterministic synthetic development data, and institution-onboarding package validation.

## Implemented components

- Six tenant-owned operational tables for jobs, attempts, dead letters, schedules, backups, and restore drills.
- PostgreSQL lease-based job claiming using `FOR UPDATE SKIP LOCKED`, exponential retry, dead-letter capture, and idempotency keys.
- API endpoints for operational job creation, status, summaries, and controlled dead-letter replay.
- Worker process with a governed handler registry and safe failure recording.
- Security headers, request-size enforcement, Redis rate limiting, production fail-closed configuration checks, and protected metrics.
- Optional ClamAV `INSTREAM` upload scanning; production configuration requires fail-closed scanning.
- JSON structured logging with recursive credential redaction and request/correlation context.
- Dependency-aware readiness checks for PostgreSQL, Redis, MinIO/S3, Qdrant, and optionally Ollama.
- Dockerfiles, hardened production Compose, Caddy gateway, Kubernetes base manifests, Prometheus configuration, and alert rules.
- PowerShell backup, checksum verification, destructive restore guard, worker start, and production-configuration validation.
- JSON Schema and semantic validator for institution onboarding packages.
- A deterministic 36-record, 12-discipline synthetic academic development corpus.

## Deliberate boundaries

The worker framework does not pretend that every domain job handler has been live-integrated. Handlers that require PostgreSQL, MinIO, Qdrant, model providers, or notification services are registered with explicit `domain_service_required` outcomes until owner-machine integration is performed. The release therefore remains **implemented and statically validated; owner-machine validation pending**.
