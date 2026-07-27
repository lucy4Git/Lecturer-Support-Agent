# Institutional Data Onboarding

## 1. Purpose

Onboard any higher-education institution without hard-coding a particular hierarchy, terminology or academic model. Onboarding is a governed sequence, not a single unrestricted upload.

## 2. Preconditions

- institution sponsor and data owner appointed;
- Institution Administrator appointed independently from the Head of Department;
- data-sharing, privacy, security and processing terms approved;
- pilot scope and success criteria agreed;
- data classes and prohibited content defined;
- secure transfer channel established;
- tenant created with isolated storage and keys/policies;
- rollback and exit plan agreed.

## 3. Onboarding workstreams

### A. Organisation and terminology
Import unit types, hierarchy, campuses, faculties/schools, departments, programmes, qualifications, modules and local labels.

### B. Identity and roles
Import authorised users, statuses and scope assignments. Bulk user import requires preview, validation and activation workflow. Do not permanently delete prior identity history.

### C. Academic configuration
Import academic calendars, credit/grading systems, teaching periods, programme/module outcomes and allocation rules.

### D. Policies and templates
Upload effective-dated policies, teaching templates, assessment templates, moderation forms and branding. Older versions remain retrievable according to permissions.

### E. Representative content
Begin with a small approved set across selected disciplines and risk classes. Validate classification, retrieval, versioning and source display before broad migration.

### F. Secure assessment content
Onboard only after restrictive workflows, encryption, named access and audit tests pass.

## 4. Supported input formats

CSV/Excel for structured catalogues; JSON for API exports; ZIP/folders for batch content; PDF, DOCX, PPTX, XLSX, images, audio and video where supported. Every batch uses a manifest or a guided metadata mapping.

## 5. Mapping process

1. Upload into quarantine.
2. Detect schema and show sample rows/files.
3. Map institution columns/labels to canonical concepts.
4. Validate identifiers and hierarchy cycles.
5. Preview creations, updates, new versions, duplicates and errors.
6. Obtain authorised confirmation.
7. Commit item-by-item with immutable version/provenance.
8. Index asynchronously.
9. Reconcile counts and produce an onboarding report.

## 6. Organisational model rules

The institution defines unit types and parent relationships. Core system roles map to local titles. A module may belong to multiple programmes or delivery sites through explicit relationships. Shared/cross-listed teaching is represented, not duplicated silently.

## 7. Content migration rules

- never overwrite existing bytes;
- exact duplicates may link to an existing version with new provenance;
- near-duplicates require a user decision;
- revised material creates a child version;
- local adaptations create related content/version records;
- canonical status requires authorised approval;
- invalid or malicious files remain quarantined.

## 8. Acceptance checklist

- tenant-isolation tests pass;
- hierarchy and terminology match institution sign-off;
- at least two independent roles tested;
- HOD can assign modules within department only;
- administrator can manage users and institutional configuration;
- lecturer can bulk upload within assigned modules;
- source and citation cards display correctly;
- content version history is complete;
- external access expires correctly;
- backups and tenant export are tested;
- training eligibility remains `MODEL_NONE` unless separately approved.

## 9. Rollback and exit

Failed batches are reversed by compensating state changes; immutable event history remains. At contract exit, provide an export of institution-owned content and metadata, revoke access, apply retention/legal-hold decisions and produce deletion evidence.
