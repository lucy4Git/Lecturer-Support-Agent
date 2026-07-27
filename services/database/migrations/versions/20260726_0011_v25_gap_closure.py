"""Add v2.5 completion-gap, enterprise-integration, evaluation, and release tables.

Revision ID: 20260726_0011
Revises: 20260726_0010
"""
from __future__ import annotations

from pathlib import Path
from typing import Sequence

from alembic import op
import sqlalchemy as sa

from services.database.models import (
    AccountChallenge,
    DatasetAcquisitionRun,
    DatasetSourceRecord,
    DeletionAction,
    DeletionRequest,
    EvaluationCampaign,
    EvaluationResponse,
    ExternalRecordMapping,
    FederatedIdentity,
    IntegrationConnection,
    IntegrationSyncRun,
    LegalHold,
    MFADevice,
    MFARecoveryCode,
    OutboundMessage,
    SSOConnection,
    UserFeedback,
)

revision: str = "20260726_0011"
down_revision: str | None = "20260726_0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

NEW_TABLES = (
    AccountChallenge.__table__,
    MFADevice.__table__,
    MFARecoveryCode.__table__,
    SSOConnection.__table__,
    FederatedIdentity.__table__,
    OutboundMessage.__table__,
    IntegrationConnection.__table__,
    IntegrationSyncRun.__table__,
    ExternalRecordMapping.__table__,
    LegalHold.__table__,
    DeletionRequest.__table__,
    DeletionAction.__table__,
    UserFeedback.__table__,
    EvaluationCampaign.__table__,
    EvaluationResponse.__table__,
    DatasetSourceRecord.__table__,
    DatasetAcquisitionRun.__table__,
)


def upgrade() -> None:
    for schema in ("iam", "governance", "operations", "privacy", "analytics"):
        op.execute(f'CREATE SCHEMA IF NOT EXISTS "{schema}"')
    bind = op.get_bind()
    op.add_column("storage_objects", sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True), schema="content")
    op.add_column("storage_objects", sa.Column("deletion_evidence_sha256", sa.String(length=64), nullable=True), schema="content")
    for table in NEW_TABLES:
        table.create(bind=bind, checkfirst=True)

    op.execute(
        "GRANT SELECT, INSERT, UPDATE, DELETE ON "
        "iam.account_challenges, iam.mfa_devices, iam.mfa_recovery_codes, "
        "iam.sso_connections, iam.federated_identities TO lsa_app"
    )
    op.execute(
        "GRANT SELECT, INSERT, UPDATE ON "
        "iam.account_challenges, iam.mfa_devices, iam.mfa_recovery_codes, "
        "iam.sso_connections, iam.federated_identities TO lsa_auth"
    )
    op.execute(
        "GRANT SELECT, INSERT, UPDATE, DELETE ON "
        "governance.outbound_messages, governance.integration_connections, "
        "governance.external_record_mappings, governance.dataset_source_records, "
        "operations.integration_sync_runs, operations.dataset_acquisition_runs, "
        "privacy.legal_holds, privacy.deletion_requests, privacy.deletion_actions, "
        "analytics.user_feedback, analytics.evaluation_campaigns, analytics.evaluation_responses "
        "TO lsa_app"
    )
    op.execute(
        "GRANT SELECT, INSERT, UPDATE ON "
        "governance.outbound_messages, governance.integration_connections, "
        "governance.external_record_mappings, governance.dataset_source_records, "
        "operations.integration_sync_runs, operations.dataset_acquisition_runs, "
        "privacy.deletion_requests, privacy.deletion_actions TO lsa_worker"
    )
    # Password reset and OIDC public flows use lsa_auth. Message bodies are
    # encrypted before storage, and the queued job payload contains only an ID.
    op.execute("GRANT USAGE ON SCHEMA governance, operations TO lsa_auth")
    op.execute("GRANT SELECT, INSERT ON governance.outbound_messages TO lsa_auth")
    op.execute("GRANT SELECT, INSERT ON operations.background_jobs TO lsa_auth")

    policy_file = Path(__file__).resolve().parents[2] / "policies" / "row_level_security.sql"
    op.execute(policy_file.read_text(encoding="utf-8"))

    # The worker may read tenant-owned rows only. The dynamic grant excludes
    # global identity tables that do not carry tenant_id; RLS remains forced.
    op.execute(
        r"""
        DO $grant_worker_read$
        DECLARE item record;
        BEGIN
          FOR item IN
            SELECT c.table_schema, c.table_name
              FROM information_schema.columns c
             WHERE c.column_name = 'tenant_id'
               AND c.table_schema IN (
                 'tenant','iam','academic','ingestion','content','conversation',
                 'ai','source','review','audit','privacy','governance','analytics','operations'
               )
             GROUP BY c.table_schema, c.table_name
          LOOP
            EXECUTE format('GRANT SELECT ON %I.%I TO lsa_worker', item.table_schema, item.table_name);
          END LOOP;
        END
        $grant_worker_read$;
        """
    )
    op.execute("GRANT SELECT ON tenant.current_institution, iam.current_tenant_users TO lsa_worker")


def downgrade() -> None:
    bind = op.get_bind()
    for table in reversed(NEW_TABLES):
        table.drop(bind=bind, checkfirst=True)
    op.drop_column("storage_objects", "deletion_evidence_sha256", schema="content")
    op.drop_column("storage_objects", "deleted_at", schema="content")
