# Qdrant payload contract — v1.6

Every private document-chunk point contains server-produced metadata. Client requests may narrow this scope but can never replace it.

Required fields:

- `tenant_id`, `document_id`, `document_version_id`, `document_chunk_id`, `chunk_index`
- `owner_user_id`, `visibility`, `is_current`, `is_deleted`
- `title`, `original_filename`, `version_number`, `document_type`, `source_type`
- `chunk_text`, `chunk_sha256`, and optional `section_title`
- optional `org_unit_id`, `programme_id`, and `module_id`

The application constructs the tenant and role-aware filter. Retrieval results are checked again against PostgreSQL permissions before they can enter an AI prompt. Superseded versions remain in PostgreSQL and object storage but are excluded from default semantic retrieval through `is_current=false`.
