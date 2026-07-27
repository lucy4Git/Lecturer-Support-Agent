# Phase 9 — v2.0 Validation Readiness Implementation Report

## Purpose

v2.0 does not add another lecturer-facing feature. It turns the cumulative v1.1–v1.9 source foundation into a controlled owner-machine validation candidate before Claude begins auditing or extending the system.

## Why this is required

Static tests cannot prove PostgreSQL row-level security, object-storage versioning, live model execution, browser responsiveness, temporary external-access enforcement, or end-to-end role behaviour. Deferring all validation without a single governed procedure would make later failures difficult to locate and could allow unsupported readiness claims.

## Implemented approach

- One PowerShell entry point runs preflight, secret safety, cumulative static validation, migrations, integration tests, service probes, web build and optional live preview.
- Docker Desktop is never started automatically.
- Runtime evidence is stored under ignored `runtime/validation/<timestamp>/`.
- Logs are redacted using locally loaded secret values before they remain as evidence.
- A Python runtime probe checks PostgreSQL, Redis, MinIO versioning, Qdrant, Ollama, API, web and optional cloud providers.
- Playwright validates the unified work area for five roles at desktop, tablet and mobile breakpoints and captures screenshots.
- A fail-closed report marks the release validated only after full runtime and live-preview success.
- Failure-triage and rollback instructions prevent partial or misleading acceptance.

## Files added

The principal additions are under `scripts/validation/`, `config/validation/`, `tests/e2e/live-preview/`, `docs/testing/`, `docs/operations/`, and `docs/architecture/uml/v2.0/`.

## Status

The harness itself is statically validated in this package. Actual owner-machine execution remains pending because this environment cannot access the user's Windows Docker engine, local Ollama installation, browser session or private provider credentials.
