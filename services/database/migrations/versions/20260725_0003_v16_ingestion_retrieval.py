"""Add v1.6 ingestion, extraction, chunking, indexing, and retrieval trace tables.

Revision ID: 20260725_0003
Revises: 20260724_0002
"""
from __future__ import annotations

from pathlib import Path
from typing import Sequence

from alembic import op

from services.database.models import (
    DocumentChunk,
    DocumentVersionTransition,
    ExtractedContent,
    IngestionJob,
    InstitutionalRetrievalTrace,
)

revision: str = "20260725_0003"
down_revision: str | None = "20260724_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

NEW_TABLES = (
    IngestionJob.__table__,
    ExtractedContent.__table__,
    DocumentChunk.__table__,
    DocumentVersionTransition.__table__,
    InstitutionalRetrievalTrace.__table__,
)


def upgrade() -> None:
    bind = op.get_bind()
    for table in NEW_TABLES:
        table.create(bind=bind, checkfirst=True)

    op.execute(
        "GRANT SELECT, INSERT, UPDATE, DELETE ON ingestion.ingestion_jobs, "
        "content.extracted_contents, content.document_chunks, "
        "content.document_version_transitions, source.institutional_retrieval_traces TO lsa_app"
    )
    policy_file = Path(__file__).resolve().parents[2] / "policies" / "row_level_security.sql"
    op.execute(policy_file.read_text(encoding="utf-8"))


def downgrade() -> None:
    bind = op.get_bind()
    for table in reversed(NEW_TABLES):
        table.drop(bind=bind, checkfirst=True)
