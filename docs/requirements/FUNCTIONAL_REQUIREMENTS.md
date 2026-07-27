# Functional Requirements

## Unified work area

- **FR-001:** Provide one conversational work area for every authorised lecturer-support task.
- **FR-002:** Infer intent and render an appropriate inline artifact without model, agent, workflow or artifact selection.
- **FR-003:** Allow edit, refine, compare, regenerate, save, version, share and export in the same conversation.
- **FR-004:** Accept text and authorised files/folders, with resumable upload where supported.
- **FR-005:** Show contextual role-authorised actions without a separate admin or artifact application.

## Teaching and assessment

- **FR-010:** Generate lesson plans, lectures, practicals, tutorials, case studies, demonstrations and learning activities for any discipline and level.
- **FR-011:** Generate quizzes, tests, assignments, examinations, projects, rubrics, marking guides, memoranda and assessment blueprints.
- **FR-012:** Map outputs to outcomes, cognitive levels, marks, duration, delivery mode and user constraints.
- **FR-013:** Review content for clarity, alignment, workload, level, duplication, accessibility, fairness and academic integrity.
- **FR-014:** Adapt by audience, duration, resources, pedagogy, language, format and discipline.

## Sources and trust

- **FR-020:** Provide useful generic responses when institutional content is absent or unnecessary.
- **FR-021:** Retrieve/display genuine external or institutional sources when claims require verification or sources are requested.
- **FR-022:** Link citations to persisted source records with title, author/organisation, date, type and link where available.
- **FR-023:** Block fabricated or unresolved citations from verified display.
- **FR-024:** Distinguish generated content, verified claims, assumptions and institution-specific requirements.
- **FR-025:** Never claim policy compliance or formal approval without evidence and authorised human action.

## Multi-institution and hierarchy

- **FR-030:** Isolate data and operations by tenant.
- **FR-031:** Let each tenant define unit types, labels, terminology and arbitrary parent-child hierarchy.
- **FR-032:** Support tenant calendars, credit/grading schemes, qualification frameworks, policies, templates and workflows.
- **FR-033:** Bind roles and content access to organisational scope and optional validity periods.

## Independent roles and leadership

- **FR-040:** Institution Administrators add/import, activate, suspend, archive and restore tenant users.
- **FR-041:** Institution Administrators assign independent roles and scopes with full audit.
- **FR-042:** Heads of Department assign/reassign courses/modules to lecturers within department scope.
- **FR-043:** Heads of Department appoint authorised coordinators/moderators, review workload/readiness and manage departmental teaching actions.
- **FR-044:** Coordinators review alignment across assigned modules/programmes.
- **FR-045:** Moderators access/review only assigned assessment packages.
- **FR-046:** External reviewers receive task-bound, time-bound, revocable, auditable access.

## Bulk upload and versioning

- **FR-050:** Show a bulk-upload action in the same role-aware interface for authorised users.
- **FR-051:** Support folders, ZIP, manifests, multi-file drag/drop and resumable ingestion where supported.
- **FR-052:** Record uploader, active role, tenant, scope, timestamp, source, checksum, classification, batch and processing result.
- **FR-053:** Never overwrite existing content; create immutable versions or new identities.
- **FR-054:** Detect exact/probable duplicates and provide non-destructive options.
- **FR-055:** Authorised users may designate a current/canonical version without deleting history.
- **FR-056:** Classify by tenant, unit, programme, module/course, document type, academic period and sensitivity.
- **FR-057:** Make failed batches resumable and preserve successfully committed items.

## Review, export and audit

- **FR-060:** Create review assignments with scope, due date, criteria, documents and allowed actions.
- **FR-061:** Store status, findings, annotations, responses, decisions and immutable history.
- **FR-062:** Immediately deny expired/revoked external access while preserving audit.
- **FR-070:** Export appropriate artifacts to DOCX, PDF, PPTX, XLSX/CSV, HTML, LMS packages or structured JSON where applicable.
- **FR-071:** Notify users of assignments, deadlines, returns, approvals, failures and access changes.
- **FR-072:** Audit authentication, authorization, role changes, uploads, versions, assignments, AI execution, citations, exports and reviews.
- **FR-073:** Provide scoped search across conversations, content, versions, sources, assignments and reviews.
