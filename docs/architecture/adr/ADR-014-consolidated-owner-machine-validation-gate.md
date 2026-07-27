# ADR-014 — Consolidated Owner-Machine Validation Gate

## Status

Accepted for v2.0.

## Context

v1.3–v1.9 implemented substantial infrastructure-dependent behaviour while runtime validation was deliberately deferred. Independent, version-specific checklists would be repetitive and could produce incomplete or contradictory evidence.

## Decision

Use one cumulative, evidence-producing owner-machine validation harness as a mandatory gate before Claude begins auditing or extending the system. Runtime evidence is generated locally, ignored by Git, redacted, and evaluated against a fail-closed release status.

Docker Desktop must be started manually. Cloud provider calls are opt-in. Live-preview testing must demonstrate every affected role and responsive breakpoint.

## Consequences

- A source implementation can no longer be described as runtime-complete without a passing report.
- Failures are easier to reproduce and triage because every stage has a dedicated log.
- The owner keeps API keys and local infrastructure on their machine.
- Validation takes longer, but removes accumulated uncertainty before commercial hardening.
