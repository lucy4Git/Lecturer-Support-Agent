"""Grant lsa_worker SELECT and DELETE on content schema tables.

Migration 0014 granted INSERT/UPDATE on all tenant tables, but the document
ingestion handler also needs:
  - SELECT on content.documents, document_versions, storage_objects,
    document_chunks, extracted_content, ingestion_jobs (and peers) to
    read the document data it processes.
  - DELETE on content.document_chunks to clear stale chunks before re-indexing.
  - SELECT on governance.audit_events (AuditService reads back inserted rows).

Revision ID: 20260814_0017
Revises: 20260814_0016
Create Date: 2026-08-14
"""
from __future__ import annotations

from alembic import op

revision = "20260814_0017"
down_revision = "20260814_0016"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # SELECT on all tables in the schemas the worker reads from
    op.execute(
        r"""
        DO $g$
        DECLARE item record;
        BEGIN
          FOR item IN
            SELECT c.table_schema, c.table_name
              FROM information_schema.columns c
             WHERE c.column_name = 'tenant_id'
               AND c.table_schema IN (
                 'content', 'conversation', 'ai', 'source', 'review',
                 'ingestion', 'academic', 'analytics', 'governance', 'operations'
               )
             GROUP BY c.table_schema, c.table_name
          LOOP
            EXECUTE format(
              'GRANT SELECT ON %I.%I TO lsa_worker',
              item.table_schema, item.table_name
            );
          END LOOP;
        END
        $g$;
        """
    )
    # DELETE on document_chunks so the worker can clear stale vectors before re-indexing
    op.execute("GRANT DELETE ON content.document_chunks TO lsa_worker;")
    # DELETE on content.extracted_contents in case a re-extraction is forced
    op.execute("GRANT DELETE ON content.extracted_contents TO lsa_worker;")
    # SELECT on iam tables the authorization service reads (defence-in-depth; 0016 already covered the join tables)
    op.execute("GRANT SELECT ON iam.role_assignments TO lsa_worker;")
    op.execute("GRANT SELECT ON iam.access_scopes TO lsa_worker;")
    op.execute("GRANT SELECT ON iam.memberships TO lsa_worker;")


def downgrade() -> None:
    op.execute("REVOKE DELETE ON content.document_chunks FROM lsa_worker;")
    op.execute("REVOKE DELETE ON content.extracted_contents FROM lsa_worker;")
