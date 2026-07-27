# Data Classification Policy

## 1. Classification dimensions

Every item receives independent labels for confidentiality, personal data, assessment security, intellectual-property rights, tenant scope and model-use eligibility. A single “private” flag is insufficient.

## 2. Confidentiality levels

| Level | Label | Examples | Minimum controls |
|---:|---|---|---|
| C0 | Public | approved public OER, public source metadata | integrity and licence tracking |
| C1 | Internal | non-sensitive teaching plans, internal templates | authenticated tenant access |
| C2 | Confidential | draft assessments, internal reviews, staff allocations | scoped access, encryption, restricted export |
| C3 | Highly Restricted | live exams, memoranda, sensitive moderator reports, security data | named access, time limits, enhanced audit, no general indexing |

The highest applicable level controls the item and its derived outputs.

## 3. Personal-data labels

- `PD0_NONE`
- `PD1_BASIC_CONTACT`
- `PD2_EMPLOYMENT_ACADEMIC`
- `PD3_STUDENT_RECORD`
- `PD4_SPECIAL_OR_HIGH_RISK`

The initial project should avoid PD3/PD4 unless a separately approved feature requires them.

## 4. Assessment-security labels

- `AS0_NOT_ASSESSMENT`
- `AS1_PUBLIC_PRACTICE`
- `AS2_DRAFT_ASSESSMENT`
- `AS3_ACTIVE_SECURE_ASSESSMENT`
- `AS4_MARKING_SECRET`
- `AS5_RELEASED_ARCHIVE`

Active secure assessments and marking secrets are excluded from shared search, analytics and model adaptation.

## 5. Rights status

- `RIGHTS_PUBLIC_DOMAIN`
- `RIGHTS_CC0`
- `RIGHTS_CC_BY`
- `RIGHTS_SHARE_ALIKE`
- `RIGHTS_NONCOMMERCIAL`
- `RIGHTS_NO_DERIVATIVES`
- `RIGHTS_INSTITUTION_OWNED`
- `RIGHTS_PERMISSION_GRANTED`
- `RIGHTS_LINK_ONLY`
- `RIGHTS_UNKNOWN`

Unknown rights block full-text model adaptation and external publication.

## 6. Model-use eligibility

- `MODEL_NONE`
- `MODEL_RUNTIME_CONTEXT_ONLY`
- `MODEL_EVALUATION_ONLY`
- `MODEL_PROMPT_EXAMPLE_APPROVED`
- `MODEL_ADAPTATION_APPROVED`

Eligibility is explicit and revocable. A public classification does not automatically imply adaptation permission.

## 7. Indexing eligibility

- exact search;
- semantic/vector search;
- source discovery;
- user-only conversation search;
- no indexing.

C3 and active assessments default to no broad semantic indexing. If semantic retrieval is required, use a dedicated restricted index and named access policy.

## 8. Derivation rules

Derived summaries, embeddings, OCR, transcripts, chunks and generated adaptations inherit the most restrictive relevant classification unless a steward approves a lower class after documented transformation. De-identification is tested, not assumed.

## 9. Classification at upload

The system proposes labels from metadata and content; the authorised user confirms uncertain or high-risk classifications. Automatic classification cannot downgrade an existing high-risk label. Bulk uploads provide batch defaults and per-item exceptions.

## 10. Reclassification

Reclassification is effective-dated, justified and audited. It never rewrites historical labels. A changed label triggers index updates, cache invalidation, access re-evaluation and, where necessary, model-provider deletion requests.

## 11. Handling matrix

| Control | C0 | C1 | C2 | C3 |
|---|---:|---:|---:|---:|
| Authentication | optional if published | required | required | required |
| Scoped authorisation | publication policy | tenant | organisational/resource | named/resource/time |
| Encryption at rest | yes | yes | yes | yes + key separation where feasible |
| External model use | approved public only | approved provider | restricted/contractual | denied by default |
| Export | public rules | tenant policy | explicit permission | named approval |
| Audit | integrity | access changes | access and export | all access and actions |
| Model adaptation | rights review | explicit approval | denied by default | prohibited |
