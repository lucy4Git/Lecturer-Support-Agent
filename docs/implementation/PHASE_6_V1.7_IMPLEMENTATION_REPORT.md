# Phase 6 — v1.7 Teaching-Output Production Implementation Report

## Status

**Implemented in source — owner-machine runtime validation pending.**

## Purpose

v1.7 turns the unified conversation into a production workflow for lecturer-facing outputs without introducing a separate artifact workspace. A request can become a lesson plan, practical, quiz, test, assignment, examination, rubric, marking guide, case study, tutorial, moderation review or departmental analysis. The output remains embedded in the conversation and can be edited, versioned, reviewed, approved, released and exported according to role and risk.

## Implemented capabilities

1. **Lecturer module context** — authorised module offerings, outcomes, academic period, qualification level, delivery mode and programme context can be selected in the conversation. Each AI request stores an immutable context snapshot.
2. **Production output blueprints** — task-specific required sections, structural parsing and quality warnings are recorded with the generated output.
3. **Inline immutable editing** — manual edits create new `output_versions`; prior versions remain auditable. Restoring an old version creates another current version rather than rewriting history.
4. **Academic workflow** — draft, under review, changes requested, approved, released and archived states are governed by explicit permissions.
5. **Assessment safety** — assessment generation is restricted to authorised academic creation roles. Answer keys, personal/student data, mark allocation, missing module context and release safety are evaluated and persisted.
6. **Exports** — Markdown, HTML, DOCX, PDF, PowerPoint and Excel are rendered from a selected version and stored as versioned objects. Student copies strip answer sections and are subject to release/safety controls.
7. **Unified UX** — module selection, editing, history, restoration, workflow actions and exports appear inside the existing ChatGPT-style work area.

## Why this design

Generated academic materials are not ordinary chat text. They need reproducibility, accountability, safe release and formal human authority. Immutable snapshots and versions explain what context and content existed at the time of generation or approval. Separate permissions prevent an Institution Administrator from automatically acquiring academic approval powers, while Heads of Department, coordinators and moderators receive only their defined academic actions.

## Main implementation locations

- Database: `services/database/models/production.py`
- Migration: `services/database/migrations/versions/20260725_0004_v17_teaching_outputs.py`
- Services: `services/api/app/services/*output*`, `module_context.py`, `assessment_safety.py`
- Routes: `services/api/app/routes/teaching_contexts.py`, `teaching_outputs.py`
- Schemas: `services/api/app/schemas/teaching_outputs.py`
- Unified UI: `apps/web/src/components/workspace-shell.tsx`
- Contracts: `packages/artifact-schemas/src/`

## Deferred runtime evidence

PostgreSQL migration/RLS, MinIO export persistence, live provider generation, browser behaviour, accessibility, performance and end-to-end role workflows require the consolidated owner-machine validation before Claude begins its audit.
