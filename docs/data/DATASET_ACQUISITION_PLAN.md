# Dataset Acquisition Plan

## 1. Objective

Acquire a lawful, diverse and auditable portfolio for generic teaching support, institutional runtime context, source verification, evaluation and safety testing. The plan does **not** authorise indiscriminate web scraping or training on institutional content.

## 2. Acquisition channels

### Channel A — Institution-provided data
Used for tenant configuration, runtime retrieval, module support, bulk upload and institutional evaluation. Requires an institutional data owner, data-sharing terms, sensitivity classification, retention rules and scope mapping.

### Channel B — Open educational resources
Used only after item-level licence verification. A repository may contain mixed licences; repository membership alone is not proof of commercial training rights.

### Channel C — Scholarly metadata and open full text
Metadata supports source discovery. Full text is acquired only when the specific work’s licence permits the intended storage, processing and product use.

### Channel D — Public standards and frameworks
Acquire official documents or metadata with recorded terms. Policy and standards content should usually support retrieval and source linking, not permanent model training.

### Channel E — Expert-authored gold data
Commission lecturers and subject experts to create or annotate lesson plans, assessments, rubrics, source-verification cases and safety benchmarks under clear contributor agreements.

### Channel F — Synthetic data
Generate fictional institution structures, module catalogues, users and workflows for development. Synthetic academic outputs require expert review and must never be represented as official institutional material.

## 3. Prioritised source classes

| Priority | Source class | Intended use | Decision rule |
|---:|---|---|---|
| 1 | Expert-authored project benchmarks | Evaluation and supervised examples | Contributor agreement and independent review |
| 1 | Institution-approved pilot materials | Runtime retrieval and workflow validation | Data-sharing agreement; no training by default |
| 1 | Open bibliographic metadata | Source discovery and verification | Record source terms and refresh schedule |
| 2 | CC0/CC BY educational resources | Curated generic corpus | Item-level attribution and compatibility review |
| 2 | Public-domain content | Curated generic corpus | Verify public-domain status by jurisdiction |
| 3 | CC BY-SA material | Retrieval or compatible derivatives | Share-alike impact reviewed |
| 3 | CC BY-NC/NC-SA material | Noncommercial research/evaluation or linked retrieval | Exclude from commercial training unless permission obtained |
| 4 | Copyrighted or unclear material | Metadata/link only | Do not ingest full text without permission |

## 4. Candidate source register

The machine-readable register is `data/manifests/dataset_acquisition_register.csv`. The initial candidates include:

- OpenAlex and Crossref for open scholarly metadata;
- DOAJ for journal/article metadata and licence discovery;
- Europe PMC for life-science metadata and licence-filtered open access content;
- SkillsCommons for vocational and workforce educational resources with item-level licence review;
- OER Commons as a discovery layer where every resource’s conditions of use are checked;
- MIT OpenCourseWare and OpenStax as high-quality educational references with noncommercial/share-alike restrictions that require commercial-use review;
- institution-contributed content under negotiated agreements;
- project-commissioned expert and synthetic datasets.

The register records verification date, official terms location, risk, permitted proposed use and approval status. It is not an automatic download list.

## 5. Acquisition workflow

1. Create a dataset proposal and owner.
2. Define intended use: discovery, retrieval, evaluation, analytics or adaptation.
3. Review licence, terms, privacy, ethics, jurisdiction and contractual restrictions.
4. Test access method and rate limits without bypassing controls.
5. Capture source snapshot metadata and checksum.
6. Land content in quarantine; do not index yet.
7. Scan malware and validate formats.
8. Extract metadata and verify licence at item level.
9. Detect duplicates and overlap with evaluation data.
10. Sample for quality, bias, discipline and educational-level coverage.
11. Approve, restrict or reject.
12. Record lineage and place in raw/curated/evaluation zone.
13. Schedule periodic revalidation of rights, links and freshness.

## 6. Institution data request package

For each tenant request:

- organisation hierarchy and terminology;
- programmes, qualifications, modules and outcomes;
- academic calendar, grading and credit rules;
- teaching and learning policies;
- assessment and moderation policies;
- approved templates;
- representative teaching resources;
- assessment examples with security classifications;
- lecturer/module assignments;
- moderation and external review workflows;
- retention, copyright and data-owner decisions;
- technical export formats and identifiers.

Student records are excluded unless a separately approved use case requires them. Pilot data should be de-identified or synthetic wherever possible.

## 7. Sampling and balance

Acquisition batches are measured against a coverage matrix crossing:

- discipline family;
- qualification level;
- teaching modality;
- assessment form;
- institution type and region;
- language and locale;
- accessibility representation;
- pedagogy;
- source authority and licence class.

Underrepresented cells trigger targeted expert authoring or additional lawful acquisition rather than uncontrolled scraping.

## 8. Annotation plan

Annotations use published guidelines, examples and calibration rounds. At least two reviewers assess high-risk or subjective benchmark items. Disagreement is adjudicated and retained as metadata. Annotation must record discipline expertise, conflicts of interest and confidence.

## 9. Data acceptance criteria

A batch is accepted only when:

- schema and checksum validation pass;
- required provenance fields are complete;
- licence status is not `unknown` for adaptation use;
- privacy and sensitivity classification is complete;
- tenant and scope are explicit;
- quality sampling meets the threshold;
- duplicate and contamination checks pass;
- security scanning is clean;
- the data owner approves intended use.

## 10. Acquisition phases

### Phase 1 — Metadata and fixtures
Build schemas, synthetic institution fixtures, source metadata connectors and evaluation case templates.

### Phase 2 — Generic benchmark corpus
Commission human-reviewed examples and collect low-risk openly licensed resources.

### Phase 3 — Pilot institution onboarding
Ingest approved configuration and teaching materials into isolated tenant storage.

### Phase 4 — Controlled model-adaptation study
Only after baseline evaluation, prepare a small rights-cleared training candidate and compare against prompt/tool baselines.

### Phase 5 — Continuous governance
Monitor quality drift, rights changes, source availability, model behaviour and dataset coverage.

## 11. Prohibited acquisition practices

- bypassing authentication, paywalls, robots controls or access restrictions;
- assuming an open website means open training rights;
- collecting personal data “just in case”;
- mixing tenant content into a shared model-training corpus;
- copying confidential examinations into development fixtures;
- using evaluation answers in prompt templates or fine-tuning data;
- ingesting sources without a deletion and provenance mechanism.
