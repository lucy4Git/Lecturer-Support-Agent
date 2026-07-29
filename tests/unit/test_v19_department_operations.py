from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import ValidationError

from services.api.app.main import app
from services.api.app.schemas.department_operations import CalendarEventCreate, ReadinessItemUpdate
from services.api.app.services.department_operations import (
    HandoverStateMachine, ReadinessCalculator, TeachingPlanStateMachine, TeachingSessionStateMachine,
    WorkloadCalculator, canonical_checksum,
)
from services.database.models import Base


def test_v19_registers_department_operations_tables() -> None:
    tables=set(Base.metadata.tables)
    assert len(tables) >= 90
    assert {
        'academic.academic_calendar_events','academic.teaching_plans','academic.teaching_plan_versions',
        'academic.teaching_sessions','academic.module_readiness_profiles','academic.module_readiness_items',
        'academic.workload_activities','academic.handover_packages','academic.handover_versions',
        'academic.handover_actions','governance.operational_alerts',
    }.issubset(tables)



def test_teaching_plan_state_machine_prevents_reopening_archived_plan() -> None:
    assert TeachingPlanStateMachine.transition('draft','activate') == 'active'
    assert TeachingPlanStateMachine.transition('active','pause') == 'paused'
    assert TeachingPlanStateMachine.transition('paused','activate') == 'active'
    with pytest.raises(ValueError): TeachingPlanStateMachine.transition('archived','activate')


def test_teaching_session_state_machine_fails_closed() -> None:
    assert TeachingSessionStateMachine.transition('planned','deliver') == 'delivered'
    assert TeachingSessionStateMachine.transition('rescheduled','cancel') == 'cancelled'
    with pytest.raises(ValueError): TeachingSessionStateMachine.transition('delivered','reschedule')


def test_handover_state_machine_preserves_correction_cycle() -> None:
    assert HandoverStateMachine.transition('draft','submit') == 'submitted'
    assert HandoverStateMachine.transition('submitted','request_changes') == 'changes_requested'
    assert HandoverStateMachine.transition('changes_requested','submit') == 'submitted'
    assert HandoverStateMachine.transition('submitted','accept') == 'accepted'
    with pytest.raises(ValueError): HandoverStateMachine.transition('draft','accept')


def test_readiness_calculator_blocks_on_incomplete_blocking_item() -> None:
    score,state,blocking=ReadinessCalculator.calculate([
        {'status':'complete','weight':2,'blocking':False},
        {'status':'missing','weight':1,'blocking':True},
    ])
    assert score == Decimal('66.67')
    assert state == 'blocked'
    assert blocking == 1


def test_readiness_calculator_handles_not_applicable_items() -> None:
    score,state,blocking=ReadinessCalculator.calculate([
        {'status':'complete','weight':1,'blocking':False},
        {'status':'not_applicable','weight':50,'blocking':True},
    ])
    assert score == Decimal('100.00') and state == 'ready' and blocking == 0


def test_workload_calculator_detects_overload() -> None:
    raw,weighted,utilisation,overloaded=WorkloadCalculator.summarise([(Decimal('20'),Decimal('1.5')),(Decimal('10'),Decimal('1'))], Decimal('35'))
    assert raw == Decimal('30') and weighted == Decimal('40')
    assert utilisation == Decimal('114.29') and overloaded


def test_calendar_event_requires_positive_duration() -> None:
    now=datetime.now(timezone.utc)
    with pytest.raises(ValidationError):
        CalendarEventCreate(academic_period_id='00000000-0000-0000-0000-000000000001', event_type='deadline', title='Invalid event', starts_at=now, ends_at=now-timedelta(hours=1))


def test_waiver_requires_reason() -> None:
    with pytest.raises(ValidationError): ReadinessItemUpdate(status='waived')


def test_canonical_checksum_is_order_independent() -> None:
    assert canonical_checksum({'b':2,'a':1}) == canonical_checksum({'a':1,'b':2})


def test_v19_routes_are_registered() -> None:
    paths = set(app.openapi()["paths"].keys())
    assert {
        '/api/v1/department-operations/calendar/events',
        '/api/v1/department-operations/teaching-plans',
        '/api/v1/department-operations/teaching-plans/{plan_id}/sessions',
        '/api/v1/department-operations/teaching-plans/{plan_id}/status',
        '/api/v1/department-operations/readiness/profiles/{profile_id}/items',
        '/api/v1/department-operations/handovers/{package_id}/versions',
        '/api/v1/department-operations/readiness/profiles',
        '/api/v1/department-operations/workloads/{user_id}',
        '/api/v1/department-operations/handovers',
        '/api/v1/department-operations/dashboards/departments/{organisational_unit_id}',
    }.issubset(paths)


def test_role_catalogue_keeps_admin_and_hod_independent() -> None:
    catalogue=json.loads(Path('services/database/seeds/role_permissions.json').read_text())
    roles={x['code']:set(x['permissions']) for x in catalogue['roles']}
    assert 'department.operations.read' in roles['head_of_department']
    assert 'workload.manage' in roles['head_of_department']
    assert 'department.operations.read' not in roles['institution_administrator']
    assert 'academic.assign_lecturer' not in roles['institution_administrator']
    assert 'workload.read_own' in roles['lecturer']
    assert 'handover.manage' not in roles['external_reviewer']
