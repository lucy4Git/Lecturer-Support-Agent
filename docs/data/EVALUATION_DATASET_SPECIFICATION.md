# Evaluation Dataset Specification

## 1. Purpose

Create an independent benchmark suite that measures whether the Lecturer Support Agent is useful, pedagogically sound, source-honest, secure and efficient across disciplines, levels, institution structures and devices.

## 2. Isolation

Evaluation cases, reference outputs and scoring rubrics are stored in a separate access-controlled zone. They are not included in prompt examples, retrieval corpora or fine-tuning data. Hash-based and semantic contamination checks run before every model-adaptation experiment.

## 3. Benchmark families

### E1 Teaching generation
Lesson plans, practicals, tutorials, cases and teaching schedules. Score alignment, feasibility, timing, inclusivity, learner level, discipline accuracy and resource realism.

### E2 Assessment generation
Quizzes, tests, assignments, exams, rubrics and marking guides. Score outcome coverage, cognitive demand, clarity, fairness, marks, answerability, rubric validity and security.

### E3 Academic alignment
Map tasks to outcomes, detect gaps/duplication and compare modules/programmes without inventing policy requirements.

### E4 Source integrity
Verify that citations exist, resolve, support claims and are appropriately authoritative. Include adversarial fake titles and DOIs.

### E5 Generic versus institution-aware behaviour
The system should answer generically when institutional context is absent, use institution data when relevant and never claim institution-specific compliance without evidence.

### E6 Role and workflow correctness
Test lecturer, coordinator, HOD, moderator, external reviewer and administrator actions with positive and negative cases.

### E7 Tenant isolation and privacy
Attempt cross-tenant retrieval, guessed IDs, malicious document references, export leakage and provider-policy violations.

### E8 Bulk upload and versioning
Test mixed file batches, duplicates, interrupted uploads, classification, historical migrations, concurrent revisions and canonical selection.

### E9 Safety and responsibility
Unsafe laboratory/clinical directions, biased assessments, academic integrity, copyright reproduction and deceptive approvals.

### E10 UX and performance
Task completion, accessibility, mobile/responsive flows, streaming, recovery, latency and user satisfaction.

## 4. Case schema

Each case follows `data/schemas/evaluation_case.schema.json` and includes prompt, role, tenant/scope, input references, expected capabilities, reference criteria, prohibited behaviours, sources, risk level, scoring rubric and threshold.

## 5. Coverage matrix

Every release reports coverage by:

- at least 12 discipline families;
- qualification levels from foundational/vocational to postgraduate;
- face-to-face, online, blended, laboratory, clinical, studio, field and WIL modes;
- multiple institution hierarchy patterns;
- common and nontraditional assessment types;
- accessibility and multilingual/locale scenarios where supported;
- low-, medium- and high-risk tasks.

No release may claim coverage for an untested category.

## 6. Human evaluation

High-impact teaching and assessment cases are scored by qualified academic reviewers. Use at least two independent raters for subjective or high-risk cases. Report agreement, adjudication and reviewer confidence. Reviewers must not score their own authored reference case without independent review.

## 7. Scoring dimensions

Common 1–5 dimensions:

- correctness;
- completeness;
- relevance;
- pedagogical quality;
- level appropriateness;
- discipline specificity;
- feasibility and resource awareness;
- inclusivity/accessibility;
- source support;
- uncertainty honesty;
- safety and confidentiality;
- structure/editability.

Automated metrics supplement, not replace, expert judgement.

## 8. Release thresholds

Initial target gates:

- zero confirmed cross-tenant disclosures;
- zero unauthorised active-assessment disclosures;
- fabricated source/identifier rate below 0.5% on citation suite, with a target of zero;
- at least 95% of high-risk factual claims linked to adequate evidence or explicit uncertainty;
- at least 90% role-policy decision accuracy;
- at least 95% immutable-version integrity across versioning tests;
- median expert score at least 4/5 on core teaching tasks;
- no critical safety regression versus previous release;
- latency and accessibility targets defined in non-functional requirements.

Thresholds must be tightened as the benchmark matures.

## 9. Statistical reporting

Report sample size, confidence intervals, task mix, model/provider/configuration, prompt and dataset versions, failures by category and subgroup. Do not hide poor performance behind a single average.

## 10. Benchmark governance

New cases are reviewed for rights, privacy, duplication and answer leakage. Retired cases remain versioned. Challenge sets may be rotated to reduce overfitting. Public demonstrations use safe cases that do not reveal restricted benchmark answers.
