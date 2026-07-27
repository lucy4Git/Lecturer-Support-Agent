# Bulk Upload Scenarios — Data Foundation

Bulk upload is a contextual button/action within the unified work area and relevant views. It is visible only when the active user has `content.bulk_upload` for the selected scope. It is not limited to the Institution Administrator.

## Common workflow

Authorize scope → create upload session → select files/folder/ZIP/manifest → apply batch defaults → resumable transfer → checksum and malware scan → extract metadata → classify sensitivity/rights/type → detect exact and near duplicates → preview decisions → confirm → commit immutable versions → index → report successes/errors/provenance.

## Scenario 1 — Institution Administrator: new institution setup

Uploads organisation catalogues, programme/module catalogues, calendars, policies, templates and user rosters. The system maps local terms, validates hierarchy, previews roles and creates effective-dated versions. No prior content is replaced.

## Scenario 2 — Institution Administrator: policy and template refresh

Uploads revised institutional policies and templates. The system identifies prior canonical versions, proposes new versions, records effective dates and requires approval before changing the canonical pointer.

## Scenario 3 — Head of Department: semester readiness pack

Uploads module descriptors, teaching plans, allocation spreadsheets, moderation schedules, laboratory guidance and handover packs for the department. The system links files to modules and lecturers and reports missing or inconsistent metadata.

## Scenario 4 — Head of Department: historical department migration

Uploads several academic years of teaching and moderation evidence. The system uses academic-period metadata, preserves all revisions, flags duplicate clusters and creates a migration reconciliation report.

## Scenario 5 — Head of Department: course allocation import

Uploads a structured allocation sheet. The system validates lecturer and module identities, overlapping dates and workload rules; shows proposed assignments; and commits authorised effective-dated assignments without deleting history.

## Scenario 6 — Lecturer: semester teaching pack

Uploads slides, notes, readings, tutorials, practicals, case studies, quizzes, rubrics and marking guides for assigned modules. The system proposes week, topic, content type and visibility. The lecturer confirms publication status.

## Scenario 7 — Lecturer: revised material after delivery

Uploads edited slides, corrected practical instructions and reflection notes. The system detects similarity, creates new versions linked to the earlier items, records the change reason and preserves previous versions for audit and handover.

## Scenario 8 — Lecturer: large multimedia module

Uploads video, audio, images, presentations and transcripts. Transfer resumes after interruption. The system stores original media, extracts technical metadata, generates authorised transcripts/derivatives and retains their derivation links.

## Scenario 9 — Module Coordinator: common assessment pack

Uploads a common assessment, rubric and memorandum for several groups or sites. Local adaptations become related versions; the original coordinator version remains intact. Active assessment security is enforced.

## Scenario 10 — Programme Coordinator: curriculum alignment evidence

Uploads programme outcomes, module outcomes, curriculum maps and assessment plans. The system builds traceable relationships and produces an alignment input set without changing source documents.

## Scenario 11 — Internal Moderator: review evidence

Uploads annotated assessments, moderation forms and findings only to assigned reviews. Feedback cannot mutate the submitted assessment version; it creates separate review evidence and findings.

## Scenario 12 — External Moderator: restricted review batch

Uploads comments and signed forms during an active assignment. The button disappears when access expires. All upload and download actions remain auditable.

## Scenario 13 — External Reviewer: evidence request response

Where explicitly granted, uploads a review report and evidence notes for a named programme/module. Files are restricted to the assignment and cannot be browsed elsewhere.

## Scenario 14 — Any authorised user: duplicate detection

An exact checksum match is found. The user may link new provenance to the existing version, create a new content identity, or cancel. A near-duplicate offers create revision, alternate/local adaptation, new item, or cancel. There is no overwrite option.

## Scenario 15 — Any authorised user: interrupted or partial batch

The browser or network fails. The upload resumes from verified chunks using idempotency keys. Completed items are not duplicated. The final report distinguishes completed, quarantined, rejected and awaiting-confirmation items.

## Scenario 16 — Any authorised user: wrong classification discovered

The item is reclassified by an authorised user. Historical classification remains in the audit trail; indexes, access and provider eligibility are recalculated.

## Scenario 17 — Data steward: rights uncertainty

A batch contains unknown licences. The content remains quarantined or link-only. It is not embedded, used for model adaptation or published until rights are resolved.

## Scenario 18 — Institution: migration from another LMS/repository

A manifest includes source IDs, historical versions and paths. The system imports original identifiers as provenance, preserves relationships and produces a source-to-target reconciliation file.

## Required reporting

Every batch report includes actor and active role, tenant/scope, timestamps, totals by status, checksums, malware results, classification confidence, rights status, duplicate decisions, created content/version IDs, failures, retry history, indexing state and audit event IDs.
