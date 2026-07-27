# Data Assets

This directory contains implementation-neutral data contracts, safe examples, migration placeholders and evaluation metadata. **Never store production institutional content, confidential assessments or personal student data in this repository.**

## Data Foundation and Model Readiness assets

- `schemas/` — Draft 2020-12 JSON Schemas for datasets, documents, versions, sources, citations, evaluation cases, bulk-upload manifests and configurable institutional structures, AI provider registries, model registries and Ollama model profiles.
- `manifests/example_dataset_manifest.json` — safe synthetic dataset-manifest example.
- `manifests/example_bulk_upload_manifest.json` — safe bulk-upload manifest example.
- `manifests/dataset_acquisition_register.csv` — candidate source and rights decision register; it does not contain downloaded datasets.
- `evaluation/example_evaluation_case.json` — held-out benchmark fixture.
- `evaluation/README.md` — evaluation-data handling rules.

## Validation

Run from the repository root:

```bash
python scripts/validation/validate_data_foundation.py
python scripts/validation/validate_multi_provider_pack.py
```

Implementation must follow `PROJECT_CONSTITUTION.md`, `docs/data/`, applicable ADRs, privacy rules and tenant-isolation controls.

## v1.3 controlled acquisition assets

- `schemas/acquisition_request.schema.json` defines the rights and approval gate.
- `manifests/example_acquisition_request.json` is intentionally unapproved and non-downloadable.
- `../scripts/data/acquire_approved_dataset.py` downloads only an explicitly approved HTTPS resource into the ignored quarantine zone.
