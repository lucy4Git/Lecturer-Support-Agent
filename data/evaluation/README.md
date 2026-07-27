# Evaluation Data

This directory contains **synthetic or explicitly approved evaluation fixtures only**. It must not contain live student records, confidential institutional assessments, production conversations, or another tenant's content.

## Included example

- `example_evaluation_case.json` — a schema-valid teaching-generation benchmark fixture.

## Operating rules

1. Keep release evaluation data separate from prompt examples, runtime retrieval corpora and any future fine-tuning data.
2. Record a contamination hash for every benchmark item before model-adaptation experiments.
3. Use fictional tenant and user identifiers unless an approved research protocol permits otherwise.
4. Require discipline experts and teaching-and-learning specialists to approve high-stakes benchmark cases.
5. Follow `docs/data/EVALUATION_DATASET_SPECIFICATION.md` and `docs/data/AI_SAFETY_AND_RED_TEAM_DATASET.md`.
