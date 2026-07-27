# ADR-013: Departmental Teaching Operations in the Unified Work Area

**Status:** Accepted  
**Date:** 2026-07-25

## Decision

Implement teaching plans, delivery sessions, readiness, workload, academic calendar events, and lecturer handover as first-class tenant-owned domains exposed through contextual actions in the single AI-native work area.

## Rationale

These are interconnected day-to-day responsibilities. Fragmenting them into separate portals would undermine the agreed ChatGPT-style experience and create duplicate navigation and permissions. They require durable structured data, immutable versioning, scope-aware authorisation, and audit evidence rather than being stored only as chat text.

## Consequences

- The Head of Department receives scoped academic operational authority without becoming Institution Administrator.
- Lecturers can manage their own module operations and continuity duties.
- Department dashboards are computed from authoritative operational records.
- Institutional terminology and hierarchy remain configurable.
- Runtime validation is mandatory before production readiness is claimed.
