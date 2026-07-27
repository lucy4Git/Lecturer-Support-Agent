# ADR-015 — Commercial Unified Workspace and Authorised Search

## Status

Accepted for v2.1.

## Decision

Search, Library, Files, Saved outputs, Notifications, conversation work, and role actions are presented inside one role-aware application shell. Search and content visibility are enforced server-side. Saved outputs store exact immutable output-version references. Notifications are tenant-owned and recipient-specific.

## Rationale

A separate workspace for each artifact or operational function would fragment the AI-native experience. Client-side global search would increase disclosure risk. Version pointers avoid changing a saved item when an output is edited later.

## Consequences

- The workspace API becomes a composition boundary across conversation, content, review, and governance domains.
- Search must remain conservative until explicit cross-user sharing contracts are introduced.
- Owner-machine RLS and browser validation are mandatory.
