# Candidate Data Source Register

**Purpose:** Planning register for lawful acquisition and source verification. Inclusion does not grant permission to ingest or train on all content.

| Source | Data type | Official rights signal verified 2026-07-21 | Proposed use | Key restriction/risk | Status |
|---|---|---|---|---|---|
| OpenAlex | scholarly metadata | CC0 | discovery, authority graph, citation metadata | API limits and metadata quality; not full-text rights | candidate-approved for technical prototype |
| Crossref | scholarly metadata | metadata broadly open for reuse | DOI resolution and metadata verification | member-supplied metadata may be incomplete; full text separate | candidate-approved |
| DOAJ | journal/article metadata | article metadata CC0; site content separate | open-access and licence discovery | verify each article licence/full text | candidate-approved |
| Europe PMC | life-science metadata and licence-filtered OA text | API and OA/licence fields | source discovery and selected evidence | apply item licence and field-specific access terms | candidate-review |
| OER Commons | OER discovery, mixed resources | item-level usage rights | discover teaching resources | mixed licences; `Read the Fine Print` items excluded | discovery-only until item review |
| SkillsCommons | workforce/vocational OER | many CC BY resources with item metadata | practical/vocational examples | embedded third-party content and individual licence review | candidate-review |
| MIT OpenCourseWare | course materials | generally CC BY-NC-SA with exclusions | noncommercial research/reference or links | noncommercial/share-alike; external resources excluded | restricted |
| OpenStax | textbooks | current library generally CC BY-NC-SA; editions may vary | linked reference, noncommercial evaluation with review | commercial model training not assumed; check edition | restricted |
| Institution-contributed data | structure, policies, teaching content | contract/data-sharing agreement | tenant runtime context and pilot evaluation | confidential, tenant isolated, no training by default | agreement required |
| Project expert-authored data | gold teaching and assessment examples | contributor agreement | benchmark and approved prompt/fine-tune examples | cost, bias and reviewer independence | high priority |
| Project synthetic fixtures | fictional institutions and workflows | project-owned | development, security, migration and E2E tests | label synthetic; expert review for pedagogy | high priority |

Machine-readable details are in `data/manifests/dataset_acquisition_register.csv`. Rights must be revalidated before automated acquisition or model use.
