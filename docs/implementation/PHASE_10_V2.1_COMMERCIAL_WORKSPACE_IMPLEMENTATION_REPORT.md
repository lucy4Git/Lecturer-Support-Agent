# Phase 10 — v2.1 Commercial Unified Workspace Implementation Report

## Purpose

v2.1 turns the existing conversation shell into the commercial navigation and knowledge experience required for daily lecturer-support work. It preserves the single ChatGPT-style work area: Search, Library, Files, Saved outputs, Notifications, and role actions are contextual views of the same application, not separate products or artifact workspaces.

## Implemented scope

- Unified role-aware navigation for conversation, search, library, files, saved outputs, and notifications.
- Server-owned navigation contract with unread notification badges.
- Tenant- and role-filtered unified search across owned conversations, generated outputs, authorised files, and assigned review tasks.
- Library and Files views built on the existing document-access service and immutable current-version records.
- Attachment of an authorised file version directly to the next conversation request.
- Personal Saved outputs linked to one exact immutable output version.
- Actionable user notifications with read/unread state and resource paths.
- Responsive commercial UI, loading/empty/error states, keyboard shortcut, and light/dark appearance.
- PostgreSQL models and Alembic migration for saved outputs and notifications.
- RLS coverage extended to the governance schema.
- v2.1 unit tests, PlantUML, API, security, UX, acceptance, and owner-machine validation documentation.

## Design rationale

Search is performed server-side because client-only filtering could reveal records already loaded outside the active user's scope. Library and Files reuse PostgreSQL authorisation after candidate selection rather than trusting vector metadata or frontend visibility. Saving an output stores a pointer to the exact output version, so later edits do not change what the user saved. Notifications are addressed to one institutional user and remain tenant-owned and auditable.

## Runtime status

**IMPLEMENTED — STATICALLY VALIDATED — OWNER-MACHINE VALIDATION PENDING.**

Live migration, PostgreSQL RLS, production Next.js build, browser workflows, mobile layouts, and seeded notification/search scenarios must be exercised through the consolidated owner-machine harness before runtime acceptance.
