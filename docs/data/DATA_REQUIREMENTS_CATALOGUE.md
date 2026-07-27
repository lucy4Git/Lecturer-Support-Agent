# Data Requirements Catalogue

## 1. Catalogue purpose

This catalogue specifies the complete categories of data needed to build, operate and evaluate the Lecturer Support Agent. It distinguishes data required for normal product operation from data that might later support model adaptation. “Required” does not mean “permitted for training.”

## 2. Universal metadata requirements

Every dataset, file, record or generated example must carry, where applicable:

- stable ID, tenant ID and organisational scope;
- title, description, language and locale;
- academic discipline and subdiscipline;
- qualification type, framework level and learner stage;
- teaching mode and pedagogical approach;
- content or assessment type;
- intended audience and prerequisite knowledge;
- learning outcomes and competencies;
- academic period and effective dates;
- author/owner, uploader and source system;
- creation, acquisition, update and review timestamps;
- licence, copyright holder, permitted purposes and restrictions;
- sensitivity, confidentiality, personal-data and assessment-security labels;
- checksum, MIME type, size, original path and object-storage version;
- quality score, review status and known limitations;
- parent version, derived-from records and provenance chain;
- retention class, legal hold and deletion eligibility;
- indexing eligibility and model-use eligibility.

## 3. Academic structure and configuration

| Requirement | Examples | Purpose |
|---|---|---|
| Tenant profile | institution name, identifiers, jurisdictions, campuses | Multi-institution boundary |
| Configurable unit types | college, faculty, school, department, centre | Any HEI hierarchy |
| Organisational relationships | parent/child, cross-listed, shared service | Scope and reporting |
| Programmes and qualifications | codes, names, levels, credits, accreditation | Teaching context |
| Courses/modules/subjects | outcomes, prerequisites, credits, contacts | Generation and assignment |
| Academic calendars | terms, blocks, examination periods | Scheduling and effective dates |
| Grading systems | marks, grades, pass rules, rounding | Assessment support |
| Role labels | local title mapped to system role | Institution terminology |
| Work allocations | lecturer, coordinator, moderator, validity | Authorisation and workload |

## 4. Teaching and learning content

Required content classes:

- course/module descriptors and study guides;
- curriculum maps and programme outcomes;
- lesson plans and teaching schedules;
- lecture notes, slides and transcripts;
- tutorials, seminars and discussion activities;
- laboratory, workshop, studio and clinical guides;
- simulations, demonstrations and fieldwork instructions;
- case studies, examples and problem sets;
- reading lists and annotated bibliographies;
- inclusive and accessible alternative formats;
- online and blended learning activities;
- work-integrated learning and placement materials;
- lecturer reflection and handover packages.

Minimum annotations include duration, group size, resources, delivery mode, outcomes, learner level, activity sequence, safety considerations, accessibility adaptations and expected evidence of learning.

## 5. Assessment content

Required assessment classes:

- diagnostic, formative and summative quizzes;
- tests, examinations and supplementary assessments;
- assignments, projects and portfolios;
- oral, practical, clinical and performance assessments;
- presentations, studio critiques and capstones;
- assessment blueprints;
- rubrics and marking guides;
- model answers and memoranda;
- question banks and item statistics;
- internal and external moderation packs;
- feedback examples and grade descriptors.

Minimum annotations include marks, duration, outcomes, competencies, cognitive demand, difficulty, assessment conditions, resources allowed, accessibility accommodations, answer rationale, rubric dimensions and moderation status.

Restricted assessment data requires a separate encryption, access and retention class.

## 6. Pedagogy and academic-principle data

The dataset portfolio must represent, without prescribing a single method:

- constructive alignment;
- active and collaborative learning;
- problem-, project-, inquiry- and case-based learning;
- competency-based education;
- experiential and work-integrated learning;
- universal design for learning and accessibility;
- inclusive teaching and culturally responsive practice;
- formative feedback and assessment for learning;
- reflective practice and metacognition;
- online, blended and flipped learning;
- laboratory, clinical, studio and field pedagogy;
- adult and professional learning;
- research-led teaching and supervision.

Each pedagogical label must include its source, definition, applicability and known limitations. The platform must not treat one taxonomy such as Bloom’s as the only valid academic framework.

## 7. Discipline coverage

At minimum, the acquisition plan must establish representative data for:

- engineering and technology;
- computing and information sciences;
- natural, mathematical and applied sciences;
- health and clinical sciences;
- business, economics and management;
- education;
- law;
- humanities, languages and theology;
- social and behavioural sciences;
- agriculture and environmental sciences;
- architecture and built environment;
- arts, design, media and performance;
- vocational, technical and professional programmes;
- interdisciplinary and emerging fields.

For each discipline, collect common teaching formats, assessment types, terminology, safety/professional requirements and evidence standards.

## 8. Generic source and citation data

The source-verification service needs:

- bibliographic metadata and persistent identifiers;
- author/organisation identities;
- publisher, venue and publication dates;
- licence and open-access status;
- URL resolution and last verification time;
- correction, retraction and version relationships;
- extracted claims or evidence passages;
- source authority and applicability labels;
- query, retrieval rank and retrieval method;
- claim-to-source support relationships.

Bibliographic metadata does not grant permission to store or train on full text. Full-text rights are evaluated separately.

## 9. Operational data

- user identities and authentication references;
- role assignments and organisational scopes;
- temporary external-access grants;
- conversations and messages;
- generated inline artifacts and edits;
- AI provider calls, model versions and prompt versions;
- upload batches and per-item statuses;
- content identities and immutable versions;
- moderation assignments, findings and responses;
- course/module assignments;
- audit events and security signals;
- export, notification and background-job records;
- consent, privacy requests and retention actions.

## 10. Evaluation and annotation data

Each benchmark case requires:

- stable case ID and immutable version;
- task and risk category;
- role, tenant and scope context;
- prompt and permitted input files;
- reference answer, required elements or rubric;
- unacceptable behaviours;
- expected sources where factual verification is required;
- scoring dimensions and thresholds;
- human raters and adjudication record;
- model/provider/configuration tested;
- results and failure taxonomy;
- contamination status.

## 11. Safety and adversarial data

Include cases for fabricated sources, prompt injection, tenant exfiltration, unauthorised assessment access, unsafe laboratory or clinical guidance, discriminatory assessment design, deceptive compliance claims, copyright over-reproduction, malicious uploads, data poisoning, role escalation, reviewer access after expiry and sensitive-data leakage.

## 12. Data not required or prohibited by default

The initial platform does not require:

- raw biometric data;
- national identity numbers;
- payment-card data;
- unrestricted student records;
- hidden surveillance data;
- private email contents unrelated to a user-initiated task;
- confidential material from another institution;
- scraped copyrighted full text without permission;
- production conversations for model training without opt-in.

## 13. Minimum pilot quantities

Quantities are quality-guided targets, not universal guarantees:

- 5–10 representative institutions as synthetic configuration fixtures before real onboarding;
- at least 12 discipline families represented in generic evaluation;
- at least 6 qualification/complexity bands;
- at least 8 teaching modalities;
- at least 10 assessment forms;
- 300+ human-reviewed generic teaching tasks;
- 300+ assessment/rubric tasks;
- 200+ source and citation cases;
- 200+ role/tenant/security cases;
- 150+ safety red-team cases;
- 50+ bulk-upload and version-history scenarios.

Pilot acceptance depends on coverage and confidence intervals, not raw counts alone.
