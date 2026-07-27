# Lecturer Support Agent Project Constitution

**Status:** Binding project governance  
**Applies to:** Product, research, design, engineering, testing, deployment, documentation, and AI-agent work

## Mission

Build a trustworthy commercial platform that improves lecturers' and academic leaders' day-to-day teaching-and-learning work through one natural-language interface. It supports creation, review, coordination, moderation, administration directly related to lecturer support, bulk ingestion, source verification, immutable versions, export, and audit without becoming a general university operating system.

## Scope boundary

### In scope

Lesson plans; lecture/tutorial/practical/laboratory/clinical/studio/fieldwork activities; quizzes, tests, assignments, projects, examinations, rubrics and memoranda; course assignment; module/programme alignment; departmental teaching oversight; moderation; handover; temporary external review; tenant configuration; bulk content upload; sources; versions; export; audit and lecturer-support analytics.

### Out of scope

Student universal tutoring, research lifecycle management, finance, HR, admissions, whole-university AI orchestration, enterprise accreditation management, or autonomous academic approval.

## Experience rules

- One unified work area handles every authorised task.
- Structured outputs render and remain editable within the same conversation.
- Role-specific actions appear contextually, not in disconnected portals.
- Users do not select AI agents, models, chains, or internal workflows.
- The experience must be responsive, accessible, touch friendly, keyboard operable, resilient, and commercially polished.

## Response and source rules

- Generic teaching-and-learning assistance is the default.
- Institutional grounding is optional and contextual.
- Displayed citations must map to genuinely retrieved and persisted source records.
- Never invent a source, policy, clause, URL, DOI, author, institutional rule, approval, or compliance claim.
- Distinguish generated content, verified facts, assumptions, recommendations, and institution-specific requirements.
- High-stakes assessments and reviews require explicit human review status.

## Universal HEI design

No institution, discipline, hierarchy, academic calendar, credit model, grading model, pedagogy, country, or qualification framework may be hard-coded. Organisational units are configurable and nestable, including campus, college, faculty, school, department, centre, programme, qualification, discipline, and module/course.

## Independent roles

Institution Administrator, Head of Department, Lecturer, Coordinator, Internal Moderator, External Moderator, and External Reviewer are independent permission bundles. One person may hold more than one only through an explicit, scoped, auditable assignment.

## Bulk upload and version integrity

Bulk upload is a permission-controlled action shown in the user's current interface when required by their duties. Every upload is append-only. New material creates a new content identity or immutable version. “Latest,” “recommended,” and “canonical” are pointers or statuses, never destructive replacement. Exact/probable duplicates are labelled and resolved non-destructively.

## Security and governance

Tenant isolation, least privilege, scoped authorization, encryption, secure defaults, malware scanning, temporary external access, revocation, audit, retention, backup, and incident response are mandatory. Assessment and personal information receive stronger classification and handling.

## Engineering and validation

Typed contracts, migrations, tests, observability, rollback, architecture decisions, and documentation are required. Every UI/UX checkpoint must be tested in live preview across affected roles and desktop, tablet, and mobile views. Known defects found in preview must be fixed before the checkpoint is reported complete.

## AI-agent responsibilities

- **Claude:** primary coding, implementation, debugging, automated testing, live-preview testing, and checkpoint evidence.
- **ChatGPT:** architecture, research advice, review, evaluation, prompt design, and beginner-friendly guidance.

Both are bound by this constitution and must not mix this repository with any other project.
