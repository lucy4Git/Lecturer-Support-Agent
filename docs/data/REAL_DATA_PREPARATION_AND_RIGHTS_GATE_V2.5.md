# Real Data Preparation and Rights Gate v2.5

## Principle

The platform does not treat “available online” as permission to download, train on, redistribute or use commercially. Real data enters the system only through a source record, rights decision, approved intended use, acquisition run and checksum manifest.

## Implemented preparation assets

- `data/catalogues/verified_oer_and_metadata_sources_v2.5.json`
- `data/schemas/dataset_source_catalogue.schema.json`
- `data/fixtures/safe/real_source_metadata_seed_v2.5.jsonl`
- governed `DatasetSourceRecord` and `DatasetAcquisitionRun` entities;
- OpenAlex and Crossref metadata connectors;
- durable `data.acquire_dataset` worker job;
- object-storage manifest and checksum recording;
- explicit separation of metadata, retrieval, evaluation and adaptation use.

## Approved automated acquisition boundary

Automated acquisition is currently limited to approved scholarly metadata. Linked publisher full text is not downloaded merely because a metadata record includes a URL or DOI.

## Source decisions

- **OpenAlex:** approved for scholarly metadata acquisition; linked content remains separately licensed.
- **Crossref:** approved for bibliographic metadata acquisition; member-supplied licence information must be assessed before content retrieval.
- **MIT OpenCourseWare:** catalogued as noncommercial-only; not included in the commercial production corpus.
- **OpenStax:** each title and edition requires a current licence and terms review; no full text is bundled.
- **OER Commons and MERLOT:** item-level rights review is required because licences vary.

## Future institution corpus

Institutional materials remain retrieval context by default. They must not be used for model adaptation unless the institution supplies explicit authority, the content owner and student-data risks are resolved, and the evaluation corpus remains separated.
