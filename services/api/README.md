# Lecturer Support Agent API — v2.1

The FastAPI service provides the cumulative multi-institution Lecturer Support Agent backend, including:

- database-enforced tenant context and scoped role authorisation;
- production-oriented authentication, active-role sessions, invitation and user administration;
- configurable institutional hierarchies and teaching assignments;
- unified AI conversations, provider-neutral routing, verified sources and citation integrity;
- immutable document ingestion, versions, authorised retrieval and bulk upload;
- teaching-output production, inline versions, exports and assessment-safety controls;
- moderation, external review, correction cycles and temporary access;
- departmental teaching plans, readiness, workload, calendar and handover operations; and
- v2.1 authorised Search, Library, Files, exact-version Saved outputs, Notifications, and role-aware navigation.

Secrets are read from the local environment or production secret manager and are never returned by provider-status endpoints. Runtime-dependent behaviour remains owner-machine validation pending.
