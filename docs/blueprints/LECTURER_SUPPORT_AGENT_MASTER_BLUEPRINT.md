# Lecturer Support Agent Master Product and Implementation Blueprint

**Version:** 1.0  
**Status:** Approved foundation  
**Primary interaction:** One unified conversational work area

## Executive vision

The Lecturer Support Agent is a multi-institutional, multi-platform system that supports authorised teaching-and-learning stakeholders across every academic discipline. A user states a goal in natural language; the platform identifies intent, role, organisational scope, academic context, source needs, risk, output type, and required tools, then presents the result in the same conversation as an editable inline artifact. Internal models, agents, routing and workflows remain invisible.

The product serves universities, universities of technology, colleges, private and distance HEIs, professional schools, multi-campus institutions and configurable equivalents, while remaining limited to lecturer support rather than becoming a general institutional operating system.

## Product outcomes

1. Reduce preparation time for high-quality teaching and assessment material.
2. Improve pedagogical, outcome, cognitive-level, timing and format alignment.
3. Support course allocation, coordination, moderation, handover and departmental oversight.
4. Provide useful generic responses while showing genuine sources where verification matters.
5. Preserve every uploaded or generated version with complete provenance.
6. Enable secure internal and temporary external collaboration.
7. Deliver a state-of-the-art experience on desktop, tablet and mobile.
8. Produce measurable gains in usefulness, trust, quality, efficiency and governance.

## Supported academic work

- Lesson plans, weekly plans, lectures, tutorials, laboratory, clinical, studio, fieldwork, practical and work-integrated activities.
- Case studies, simulations, demonstrations, inclusive learning adaptations and reflective tasks.
- Quizzes, tests, assignments, projects, examinations, portfolios, oral/practical assessment, rubrics, memoranda and assessment blueprints.
- Outcome mapping, cognitive distribution, workload, clarity, level, fairness, accessibility and academic-integrity review.
- Programme/module alignment, teaching readiness, course assignment, moderation, handover and departmental teaching activity.

## Independent roles

### Lecturer
Generates, edits, versions, shares and exports teaching and assessment material within assigned scope; may bulk-upload module resources and evidence.

### Module or Programme Coordinator
Reviews alignment across assigned modules/programmes and coordinates shared content.

### Head of Department
Assigns/reassigns courses, appoints authorised coordinators/moderators, reviews workload/readiness and departmental activity, coordinates handover and bulk-uploads department content. This role does not inherit Institution Administrator permissions.

### Institution Administrator
Manages tenant users, independent role assignments, organisational structures, terminology, policies, templates, onboarding and tenant audit. This role does not inherit Head of Department or confidential academic-content authority.

### Internal or External Moderator
Reviews only assigned assessment packages and uploads feedback within the assignment scope.

### External Reviewer
Receives limited, temporary, task-bound, revocable and auditable access to explicitly assigned content and actions.

## One unified work area

The platform shall not split work into separate lesson-plan, rubric, test, report or moderation applications. It provides conversation history/search, a responsive composer, file/folder upload, streaming responses, inline source indicators, editable structured outputs, version history, contextual actions and exports inside the same conversation. A split or expanded view on large screens remains part of the same work area and conversation state.

## AI response model

- **Generic mode:** useful teaching-and-learning output without needing tenant documents.
- **Institution-aware mode:** applies authorised institutional rules, templates and content when relevant.
- **Combined mode:** combines generic knowledge, current external sources, user uploads and institutional context, clearly labelling source types.
- Every displayed citation must be verified. The AI may not label its own output approved, official or compliant without evidence and authorised human action.

## Universal multi-institution model

Each tenant defines its own unit types, hierarchy, labels, calendar, credits, grading, policies, templates and workflows. Examples include Institution → College → School → Department → Programme → Course, or University → Faculty → Department → Qualification → Module. Role assignments and content are bound to stable organisational-unit IDs and optional validity periods.

## Multi-platform strategy

A responsive web application and installable PWA form the initial commercial client. It supports adaptive navigation, touch, keyboard, screen readers, low-bandwidth behaviour, resumable upload and secure cross-device continuity. Shared APIs allow future native clients without redesigning the core.

## Bulk upload scenarios

- Institution Administrator: onboarding, user rosters, policies, templates, catalogues and annual refresh.
- Head of Department: department module packs, allocation sheets, schedules, moderation evidence and handover archives.
- Lecturer: slides, notes, readings, tutorials, practicals, assessments, rubrics, marking guides and teaching evidence.
- Coordinator: programme maps, module descriptors, common assessments, shared rubrics and alignment evidence.
- Moderator/External Reviewer: assigned annotations, forms, findings and evidence where explicitly permitted.

Every batch is resumable, scanned, classified, duplicate-checked, audited and committed item-by-item as new immutable content versions or identities. Existing material is never overwritten.

## Architecture summary

1. Responsive web/PWA and future mobile clients.
2. API gateway/BFF and streaming channel.
3. Identity, tenant, configurable organisational hierarchy and policy authorization.
4. Conversation and inline artifact capability.
5. AI orchestration, provider gateway, source discovery/verification and validation.
6. Teaching, assessment, course assignment, alignment, moderation, review, export and notification domains.
7. Bulk ingestion, malware scanning, classification, duplicate detection, version/provenance, object storage, relational metadata, search and vector indexing.
8. Audit, analytics, observability, feature flags, secrets, backup and disaster recovery.

## Delivery phases

0. Governance and repository foundation.
1. Tenant, identity, hierarchy and independent roles.
2. Unified commercial UX shell.
3. Generic AI and verifiable sources.
4. Lecturer teaching and assessment capabilities.
5. Bulk ingestion and immutable versions.
6. Coordination and Head of Department workflows.
7. Moderation and external review.
8. Export, integration, analytics and hardening.
9. Pilot evaluation and commercial readiness.

## Success measures

Task completion, lecturer time saved, pedagogical quality, assessment alignment, source correctness, fabricated-reference rate, role compliance, tenant isolation, version integrity, upload success/recovery, usability, accessibility, latency, throughput, availability, scalability and cost.
