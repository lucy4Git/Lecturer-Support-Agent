"""Add v1.9 departmental teaching operations and continuity management.

Revision ID: 20260725_0006
Revises: 20260725_0005
"""
from __future__ import annotations

from pathlib import Path
from typing import Sequence

from alembic import op

from services.database.models import (
    AcademicCalendarEvent, HandoverAction, HandoverPackage, HandoverVersion,
    ModuleReadinessItem, ModuleReadinessProfile, OperationalAlert,
    TeachingPlan, TeachingPlanVersion, TeachingSession, WorkloadActivity,
)

revision: str = "20260725_0006"
down_revision: str | None = "20260725_0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

NEW_TABLES=(
    AcademicCalendarEvent.__table__, TeachingPlan.__table__, TeachingPlanVersion.__table__,
    TeachingSession.__table__, ModuleReadinessProfile.__table__, ModuleReadinessItem.__table__,
    WorkloadActivity.__table__, HandoverPackage.__table__, HandoverVersion.__table__,
    HandoverAction.__table__, OperationalAlert.__table__,
)

def upgrade() -> None:
    bind=op.get_bind()
    for table in NEW_TABLES: table.create(bind=bind, checkfirst=True)
    op.execute(
        "GRANT SELECT, INSERT, UPDATE, DELETE ON academic.academic_calendar_events, "
        "academic.teaching_plans, academic.teaching_plan_versions, academic.teaching_sessions, "
        "academic.module_readiness_profiles, academic.module_readiness_items, academic.workload_activities, "
        "academic.handover_packages, academic.handover_versions, academic.handover_actions, "
        "governance.operational_alerts TO lsa_app"
    )
    policy_file=Path(__file__).resolve().parents[2]/"policies"/"row_level_security.sql"
    op.execute(policy_file.read_text(encoding="utf-8"))

def downgrade() -> None:
    bind=op.get_bind()
    for table in reversed(NEW_TABLES): table.drop(bind=bind, checkfirst=True)
