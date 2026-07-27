# ADR-019 — Completion Gap Closure and Enterprise Boundaries

## Status

Accepted for v2.5; runtime and institutional validation pending.

## Decision

The platform will close commercially important gaps through provider-neutral, tenant-scoped contracts rather than hard-coding one institution or vendor. OIDC is the first implemented enterprise SSO protocol. Canvas, Moodle and OneRoster are first-party academic integration adapters; a constrained generic REST adapter covers approved systems until a dedicated adapter is justified.

Credentials are referenced by environment-variable or secret-manager identifiers and are never stored as tenant configuration values. Integration data is staged and mapped before canonical adoption. Account recovery, MFA, legal holds, deletion, tenant-scoped backup, evaluation and data-source rights are first-class audited domains.

Real-source acquisition is metadata-only by default. Full text enters the system only after a source-level or item-level licence and intended-use decision. Citation coverage is verified without claiming automated semantic entailment.

## Consequences

- Institutions can integrate incrementally without changing the unified user experience.
- Tenant and role boundaries remain enforceable.
- Some deployment-specific work remains configuration and validation rather than generic code.
- Legal templates and source rights require human approval.
