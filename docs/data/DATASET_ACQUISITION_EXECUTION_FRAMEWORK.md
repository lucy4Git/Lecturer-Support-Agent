# Dataset Acquisition Execution Framework

## Purpose

This framework turns the v1.2 acquisition register into a controlled operational
workflow. It does not authorise indiscriminate scraping or model training.

## Acquisition states

`proposed -> rights_review -> academic_review -> security_review -> approved -> quarantined_download -> validated -> catalogued -> authorised_use -> retired`

## Required approval evidence

Every acquired dataset must have:

- a stable source URL or institutional transfer identifier;
- owner/publisher and licence evidence;
- permitted uses: retrieval, evaluation, adaptation, or prohibited;
- discipline and qualification coverage;
- personal/confidential data assessment;
- checksum and acquisition timestamp;
- extraction and transformation record;
- quality and bias review;
- train/evaluation separation decision; and
- retention and deletion rule.

## Storage zones

- `quarantine`: downloaded but not trusted or indexed;
- `validated-public`: approved openly licensed material;
- `institution-private`: tenant-controlled material, excluded from shared training by default;
- `evaluation-holdout`: inaccessible to training/adaptation workflows;
- `rejected`: retained only as an audit record where lawful.

## Execution safeguard

No source is downloaded merely because it appears in the planning register. A
human rights decision and a machine-readable approved manifest are required
first. Institutional documents remain runtime context by default and are not
used to train shared models without explicit lawful approval.
