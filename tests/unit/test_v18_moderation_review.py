from __future__ import annotations

import json
from pathlib import Path
from uuid import uuid4

import pytest

from services.api.app.main import app
from services.api.app.services.generated_outputs import GeneratedOutputService
from services.api.app.services.moderation_review import (
    ExternalReviewScope,
    ReviewStateMachine,
)
from services.database.models import Base
from services.database.models.enums import OutputWorkflowStatus, ReviewTaskStatus


def test_v18_registers_review_domain_tables() -> None:
    tables = set(Base.metadata.tables)
    assert len(tables) >= 90
    assert {
        "review.review_cycles",
        "review.review_packs",
        "review.review_pack_items",
        "review.review_findings",
        "review.review_finding_responses",
        "review.review_submissions",
        "review.review_decisions",
        "review.review_correction_rounds",
    }.issubset(tables)


def test_task_state_machine_is_fail_closed() -> None:
    assert ReviewStateMachine.task_transition("assigned", "accept") == ReviewTaskStatus.ACCEPTED.value
    assert ReviewStateMachine.task_transition("accepted", "start") == ReviewTaskStatus.IN_PROGRESS.value
    assert ReviewStateMachine.task_transition("in_progress", "submit") == ReviewTaskStatus.SUBMITTED.value
    with pytest.raises(ValueError):
        ReviewStateMachine.task_transition("assigned", "submit")


@pytest.mark.parametrize(
    ("decision", "action", "cycle_status"),
    [
        ("approved", "approve", "approved"),
        ("approved_with_conditions", "request_changes", "conditionally_approved"),
        ("changes_required", "request_changes", "changes_requested"),
        ("rejected", "reject", "rejected"),
    ],
)
def test_review_decision_mapping(decision: str, action: str, cycle_status: str) -> None:
    assert ReviewStateMachine.output_action_for_decision(decision) == action
    assert ReviewStateMachine.cycle_status_for_decision(decision) == cycle_status


def test_external_review_scope_requires_action_and_exact_boundary() -> None:
    output_id, version_id, cycle_id = uuid4(), uuid4(), uuid4()
    scope = {
        "generated_output_id": str(output_id),
        "output_version_id": str(version_id),
        "review_cycle_id": str(cycle_id),
    }
    identifiers = {
        "generated_output_id": output_id,
        "output_version_id": version_id,
        "review_cycle_id": cycle_id,
    }
    assert ExternalReviewScope.permits(
        allowed_actions=["review.task.perform"],
        resource_scope=scope,
        action="review.task.perform",
        identifiers=identifiers,
    )
    assert ExternalReviewScope.permits(
        allowed_actions=["review.task.perform"],
        resource_scope=scope,
        action="review.finding.create",
        identifiers=identifiers,
    )
    assert not ExternalReviewScope.permits(
        allowed_actions=["review.task.read"],
        resource_scope=scope,
        action="review.task.perform",
        identifiers=identifiers,
    )
    assert not ExternalReviewScope.permits(
        allowed_actions=["review.task.perform"],
        resource_scope={**scope, "output_version_id": str(uuid4())},
        action="review.task.perform",
        identifiers=identifiers,
    )


def test_rejected_output_can_be_reopened_as_new_draft() -> None:
    transitions = GeneratedOutputService.TRANSITIONS
    assert transitions[(OutputWorkflowStatus.UNDER_REVIEW.value, "reject")] == OutputWorkflowStatus.REJECTED.value
    assert transitions[(OutputWorkflowStatus.REJECTED.value, "return_to_draft")] == OutputWorkflowStatus.DRAFT.value


def test_review_routes_are_registered() -> None:
    paths = {getattr(route, "path", "") for route in app.routes}
    assert {
        "/api/v1/reviews/cycles",
        "/api/v1/reviews/cycles/{cycle_id}",
        "/api/v1/reviews/tasks",
        "/api/v1/reviews/cycles/{cycle_id}/findings",
        "/api/v1/reviews/tasks/{task_id}/accept",
        "/api/v1/reviews/tasks/{task_id}/findings",
        "/api/v1/reviews/tasks/{task_id}/submit",
        "/api/v1/reviews/cycles/{cycle_id}/decision",
        "/api/v1/reviews/cycles/{cycle_id}/resubmit",
        "/api/v1/reviews/dashboard/departments/{organisational_unit_id}",
        "/api/v1/external-access/grants/{grant_id}/revoke",
    }.issubset(paths)


def test_role_catalogue_preserves_independent_academic_review_authority() -> None:
    catalogue = json.loads(Path("services/database/seeds/role_permissions.json").read_text())
    roles = {item["code"]: set(item["permissions"]) for item in catalogue["roles"]}
    assert "review_decisions.record" not in roles["institution_administrator"]
    assert "review_decisions.record" in roles["head_of_department"]
    assert "review_tasks.perform" in roles["internal_moderator"]
    assert "review_tasks.perform" in roles["external_moderator"]
    assert "review_tasks.perform" in roles["external_reviewer"]
    assert "review_cycles.manage" not in roles["external_reviewer"]
