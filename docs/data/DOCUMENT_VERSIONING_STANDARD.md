# Document Versioning Standard

## 1. Purpose

Prevent data loss, silent replacement and uncertain provenance. The standard applies to institutional materials, lecturer uploads, policies, assessments, generated exports, source snapshots, datasets and machine-extracted derivatives.

## 2. Core concepts

- **Content Item:** stable conceptual identity, e.g. “IoT Sensor Practical Guide”.
- **Content Version:** immutable representation at a point in time.
- **Object Version:** object-storage version containing exact bytes.
- **Relationship:** derived-from, supersedes, alternative, duplicate, translated-from, local-adaptation or approved-copy.
- **Canonical Pointer:** currently approved version for a scope and purpose.
- **Latest Pointer:** highest committed version sequence, not necessarily approved.

## 3. Creation rules

A new version is created when bytes, meaningful metadata, effective dates, rights, sensitivity, learning outcomes or approval status change. Minor UI labels that do not change the underlying record may use metadata events, but must remain auditable.

## 4. Required fields

- content item and version IDs;
- tenant and organisational scope;
- monotonically increasing version sequence within item;
- parent/base version and relationship type;
- object key, object version, checksum, MIME and size;
- author/owner and uploader identity snapshot;
- uploader’s active role and delegated authority;
- creation, upload, effective and academic-period dates;
- source system, source ID, original path and upload batch;
- title, content type, discipline, level, language and associations;
- confidentiality, personal-data, assessment-security and rights labels;
- lifecycle, review, publication and indexing states;
- change reason and user comment;
- model-use eligibility and permitted purposes;
- audit event and provenance links.

## 5. State model

`QUARANTINED → VALIDATED → AWAITING_CONFIRMATION → COMMITTED → INDEXING → AVAILABLE`

Additional states: `RESTRICTED`, `SUPERSEDED`, `ARCHIVED`, `REJECTED`, `PURGE_PENDING`, `PURGED_TOMBSTONE`.

Rejected or purged content never disappears without a minimal tombstone and audit record, subject to legal requirements.

## 6. Duplicate decisions

### Exact checksum
- link new provenance to existing version;
- create distinct content identity if context requires;
- cancel.

### Near duplicate
- create child revision;
- create alternate/local-adaptation relationship;
- create distinct item;
- cancel.

The system must explain consequences before confirmation.

## 7. Concurrency

Use optimistic concurrency with the base version. If two users edit the same version, preserve both branches or require an explicit merge; never last-write-wins silently.

## 8. Canonical approval

Only a role with `content.set_canonical` for the scope can change the canonical pointer. The action records reason, previous/new version and effective date. Lecturer working versions do not automatically replace an institution-approved version.

## 9. Generated artifacts

Every generated artifact stores model, prompt, tool, source-evidence and input-version provenance. User edits create new versions. Exporting to DOCX/PDF does not replace the editable source artifact; it creates an export record linked to the source version.

## 10. Source snapshots

When evidence is retrieved, store source metadata, URL, retrieval time, hash where lawful, evidence passage and source version. If the external source changes, create a new source snapshot/version and retain the citation relationship to the version actually used.

## 11. Retention and purge

Archive hides content from normal use without altering version history. Purge requires retention authority and checks for legal holds, active citations, reviews and derivative obligations. Derived indexes and caches are removed. The audit tombstone does not retain the prohibited content.

## 12. Acceptance tests

- uploading the same filename with changed bytes creates a new version;
- one user cannot overwrite another user’s material;
- canonical and latest can point to different versions;
- reverting creates a new controlled version/pointer event;
- duplicate linking retains both upload provenance events;
- source citations remain tied to the exact source version;
- concurrent edits do not lose either user’s changes;
- deletion removes serving copies while preserving allowed audit evidence.
