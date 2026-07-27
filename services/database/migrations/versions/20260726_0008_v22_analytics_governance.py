"""Add v2.2 analytics, reporting, AI governance, audit centre, and settings.

Revision ID: 20260726_0008
Revises: 20260725_0007
"""
from __future__ import annotations

from pathlib import Path
from typing import Sequence

from alembic import op

from services.database.models import (
    AIUsageDaily,
    AIUsagePolicy,
    AnalyticsSnapshot,
    AuditExportJob,
    InsightAlert,
    PlatformSetting,
    ReportDefinition,
    ReportRun,
)

revision: str = "20260726_0008"
down_revision: str | None = "20260725_0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

NEW_TABLES = (
    PlatformSetting.__table__,
    AIUsagePolicy.__table__,
    AIUsageDaily.__table__,
    AnalyticsSnapshot.__table__,
    ReportDefinition.__table__,
    ReportRun.__table__,
    InsightAlert.__table__,
    AuditExportJob.__table__,
)


def upgrade() -> None:
    op.execute('CREATE SCHEMA IF NOT EXISTS "analytics"')
    op.execute('GRANT USAGE ON SCHEMA analytics TO lsa_app')
    bind = op.get_bind()
    for table in NEW_TABLES:
        table.create(bind=bind, checkfirst=True)
    op.execute(
        "GRANT SELECT, INSERT, UPDATE, DELETE ON "
        "governance.platform_settings, governance.ai_usage_policies, "
        "analytics.ai_usage_daily, analytics.analytics_snapshots, "
        "analytics.report_definitions, analytics.report_runs, analytics.insight_alerts, "
        "audit.audit_export_jobs TO lsa_app"
    )
    op.execute(
        "ALTER DEFAULT PRIVILEGES IN SCHEMA analytics "
        "GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO lsa_app"
    )
    policy_file = Path(__file__).resolve().parents[2] / "policies" / "row_level_security.sql"
    op.execute(policy_file.read_text(encoding="utf-8"))


def downgrade() -> None:
    bind = op.get_bind()
    for table in reversed(NEW_TABLES):
        table.drop(bind=bind, checkfirst=True)
    op.execute('DROP SCHEMA IF EXISTS "analytics" CASCADE')
