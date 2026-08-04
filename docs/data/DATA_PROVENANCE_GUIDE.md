# Data Provenance Guide

**Project:** Lecturer Support Agent  
**Version:** 2.5.1  
**Date:** 2026-08-03

## What is Provenance?

Provenance records the complete chain of custody for every dataset: where it came
from, how it was acquired, who approved it, what transformations were applied, and
where it currently lives in the system.

## Provenance Fields (per dataset)

Every dataset entry in `data/catalogue/dataset_catalogue.yaml` must record:

- `source_organisation`: the authoritative publisher
- `official_source_url`: the canonical URL at the publisher's own domain
- `download_url_or_api`: the actual download endpoint or API
- `access_date`: when Claude or the operator verified the source
- `publication_date`: when the source was originally published
- `provenance`: free-text description of how the rights were verified
- `sha256_checksum`: cryptographic fingerprint of the downloaded file

## Provenance for Qdrant Payloads

Every chunk in Qdrant must carry:

```json
{
  "tenant_id": "<tenant_uuid>",
  "dataset_id": "DS-XXX",
  "document_id": "<uuid>",
  "document_version_id": "<uuid>",
  "rights_status": "APPROVED_FOR_PRODUCTION",
  "approval_status": "APPROVED",
  "academic_discipline": ["education"],
  "qualification_level": ["bachelor"],
  "access_scope": "institution",
  "visibility": "authenticated",
  "source_provenance": "OpenStax CC BY 4.0 — openstax.org"
}
```

## Provenance for AI Responses

The citation integrity rule states: **a displayed citation must originate from a
retrieval associated with the same AI request**. Claude must not fabricate sources,
DOIs, author names, publication dates, or policy claims.

When the AI generates a response:
1. Source metadata is retrieved from Qdrant with the correct provenance payload
2. Only retrieved sources are cited — no hallucinated references
3. The provenance chain is logged in the audit table

## What Claude Must Never Do

- Fabricate a licence, owner, source, DOI, URL or approval
- Claim a policy exists without a verifiable source
- Self-approve institution-specific confidential data
- Report a dataset as ingested when it has not passed the ingestion pipeline
