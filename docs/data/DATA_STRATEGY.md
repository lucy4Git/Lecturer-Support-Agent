# Data Strategy

## 1. Purpose

This strategy defines how the Lecturer Support Agent will acquire, govern, store, retrieve, evaluate and, only where justified, use data for model adaptation. The objective is a productive and trustworthy platform that supports lecturers, coordinators, Heads of Department, moderators, external reviewers and institution administrators across any higher-education structure and academic field.

## 2. Product data principles

### 2.1 Generic intelligence first
The system must answer general teaching-and-learning requests even when no institutional documents exist. Generic answers may use model knowledge, tools and verified external sources. Institutional retrieval is applied only when it materially improves relevance, personalisation, policy alignment or evidence.

### 2.2 No uncontrolled training
Institutional documents, confidential assessments, user uploads, conversations, generated outputs and review comments are excluded from model training unless the institution and affected data subjects have explicitly opted in under an approved purpose, legal basis, licence, retention period and de-identification plan.

### 2.3 Data minimisation and separation
Collect only data needed for the stated task. Separate tenants, sensitivity levels, operational records, evaluation data, fine-tuning data and analytics data. Do not reuse data merely because it is technically available.

### 2.4 Provenance over volume
A smaller corpus with verified rights, subject coverage, educational level, quality labels and traceable provenance is more valuable than a large uncontrolled scrape.

### 2.5 Version everything important
Documents, metadata, policies, templates, datasets, prompts, evaluation cases and model configurations must be versioned. Historical evidence remains immutable and auditable.

### 2.6 Evidence before adaptation
Prompting, structured output schemas, retrieval, source verification and tool use must be benchmarked before fine-tuning. Fine-tuning is approved only when repeated evaluation demonstrates a stable gap that cannot be resolved more safely or cheaply.

## 3. Data domains

| Domain | Purpose | Primary examples | Default training status |
|---|---|---|---|
| Public educational resources | Generic teaching content and examples | Open textbooks, lesson plans, practical guides | Eligible only after item-level rights review |
| Scholarly metadata | Source discovery and citation verification | DOI, title, author, publisher, retraction/correction links | Eligible for indexing; not equivalent to full-text rights |
| Institutional configuration | Tenant-specific structure and terminology | Faculties, schools, departments, programmes, modules | Runtime configuration only |
| Institutional academic content | Contextual teaching and assessment support | Module guides, templates, policies, rubrics | Retrieval only by default |
| Restricted assessment content | Secure assessment preparation and moderation | Exams, memoranda, moderator reports | Never train by default |
| Interaction data | Product continuity and support | Conversations, feedback, edits | Operational use only by default |
| Evaluation data | Independent measurement | Gold lesson plans, citation tests, RBAC tests | Test-only; never train |
| Safety data | Red-team and guardrail testing | Prompt injection, unsafe lab, exfiltration cases | Test and defence development only |
| Synthetic data | Coverage expansion where lawful data is scarce | Fictional institutions, generated tasks | Labelled synthetic; human-reviewed |

## 4. Data lifecycle

1. **Plan:** define purpose, data owner, permitted uses, risks, acceptance criteria and exit conditions.
2. **Acquire:** use approved connectors, institutional upload or authorised public sources; capture licence and provenance at entry.
3. **Quarantine:** malware scan, file validation, checksum, rights status and sensitivity classification.
4. **Normalize:** extract text and metadata without altering the original object.
5. **Curate:** deduplicate, label discipline, qualification level, pedagogy, language, modality and quality.
6. **Approve:** data steward confirms use class: runtime retrieval, evaluation, analytics, adaptation, or reject.
7. **Store:** persist immutable originals and versions with tenant-scoped metadata.
8. **Index:** create search and vector indexes only after authorisation.
9. **Use:** enforce role, tenant, purpose and time constraints at query and generation time.
10. **Monitor:** record use, citation evidence, quality drift, licence changes and data incidents.
11. **Archive or purge:** apply retention schedules, legal holds and auditable tombstones.

## 5. Dataset portfolio

The minimum portfolio is intentionally diverse across:

- discipline and professional field;
- qualification and complexity level;
- teaching mode: face-to-face, online, blended, laboratory, studio, clinical, field and work-integrated learning;
- assessment form;
- pedagogy and accessibility approach;
- institutional structure and terminology;
- language, region and cultural context;
- high-resource and low-resource settings;
- source type and authority.

Coverage must be measured and declared. The platform must not claim universal quality in a field, language or jurisdiction that has not been evaluated.

## 6. Data quality dimensions

Every curated dataset receives measurable values for:

- provenance completeness;
- licence certainty;
- accuracy and authority;
- educational relevance;
- level appropriateness;
- discipline coverage;
- representativeness and bias risk;
- freshness and effective date;
- structural completeness;
- duplicate/near-duplicate status;
- privacy and confidentiality risk;
- annotation agreement;
- machine readability and accessibility.

A dataset failing a mandatory threshold remains quarantined or is restricted to research review.

## 7. Data products

The programme will maintain these governed data products:

1. **Academic task taxonomy** for intent and output routing.
2. **Teaching-content corpus** for generic examples and retrieval.
3. **Assessment-design corpus** with cognitive level and outcome labels.
4. **Rubric and marking-guide corpus** with structural annotations.
5. **Pedagogy and accessibility corpus**.
6. **Institutional configuration registry**.
7. **Source and citation authority graph**.
8. **Evaluation benchmark suite**.
9. **Safety and adversarial suite**.
10. **Synthetic multi-institution fixture set** for development without real personal data.

## 8. Model-readiness gates

A dataset is model-ready only when:

- schema validation passes;
- source and licence are recorded;
- permitted purpose includes the intended use;
- privacy review is complete;
- tenant scope is explicit;
- quality and representativeness thresholds pass;
- contamination against evaluation sets is checked;
- train/validation/test split is reproducible;
- annotator guidance and agreement are documented;
- dataset card and known limitations are approved;
- rollback and deletion obligations can be honoured.

## 9. Initial implementation order

1. Machine-readable metadata and version schemas.
2. PostgreSQL tenant, organisational, content, provenance and source models.
3. Object-storage and quarantine conventions.
4. Bulk ingestion with immutable versioning.
5. Search and source-verification indexes.
6. Safe synthetic fixtures and benchmark harness.
7. Generic AI baseline evaluation.
8. Institutional pilot acquisition after approvals.
9. Fine-tuning study only if baseline gaps justify it.

## 10. Ownership and decisions

The project owner approves scope and major implementation decisions. A future institutional Data Owner authorises tenant content; a Data Steward manages quality and metadata; Security and Privacy reviewers approve restricted uses; Academic Subject Matter Experts validate pedagogy and discipline quality; the Model Evaluation Lead controls benchmark isolation.
