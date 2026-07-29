from __future__ import annotations

import io
import json
import zipfile
from pathlib import Path

import pytest
from fastapi import HTTPException

from services.api.app.ai.contracts import TeachingTaskType
from services.api.app.ai.prompt_builder import PromptBuilder
from services.api.app.ai.task_classifier import TeachingTaskClassifier
from services.api.app.main import app
from services.api.app.services.assessment_safety import AssessmentSafetyEvaluator
from services.api.app.services.export_generation import ExportRenderer, safe_export_filename
from services.api.app.services.teaching_output_workflow import TeachingOutputWorkflow
from services.database.models import Base
from services.database.models.enums import ExportAudience, ExportFormat, SafetyReviewStatus


def test_v17_registers_production_workflow_tables() -> None:
    tables = set(Base.metadata.tables)
    assert len(tables) >= 69
    assert {
        "academic.module_context_snapshots",
        "conversation.output_lifecycles",
        "conversation.output_workflow_actions",
        "review.assessment_safety_reviews",
        "content.export_jobs",
    }.issubset(tables)


def test_assessment_generation_is_limited_to_academic_creation_roles() -> None:
    guard = AssessmentSafetyEvaluator()
    guard.enforce_generation_role(TeachingTaskType.EXAMINATION, "lecturer")
    with pytest.raises(HTTPException) as exc:
        guard.enforce_generation_role(TeachingTaskType.EXAMINATION, "external_reviewer")
    assert exc.value.status_code == 403


def test_assessment_safety_detects_answers_and_personal_data() -> None:
    result = AssessmentSafetyEvaluator().evaluate(
        task_type=TeachingTaskType.TEST,
        content="# Test\nStudent Number: 12345678\n## Answer Key\n1. Sensor A [10 marks]",
        detected_total_marks=20,
        module_context_available=False,
    )
    assert result.status == SafetyReviewStatus.BLOCKED
    assert result.answers_detected is True
    assert result.personal_data_detected is True
    assert result.student_copy_safe is False
    assert result.blocked_reasons


def test_assessment_safety_requires_review_for_generic_exam_draft() -> None:
    result = AssessmentSafetyEvaluator().evaluate(
        task_type=TeachingTaskType.EXAMINATION,
        content="# Examination\n## Instructions\nAnswer all questions.\n## Questions\n1. Explain IoT. [20 marks]",
        detected_total_marks=20,
        module_context_available=False,
    )
    assert result.status == SafetyReviewStatus.REQUIRES_REVIEW
    assert result.risk_level.value == "high"
    assert any("module context" in warning.lower() for warning in result.warnings)


def test_student_copy_removes_answer_sections() -> None:
    markdown = "# Quiz\n## Questions\n1. What is IoT?\n## Answer Key\n1. Internet of Things\n## Lecturer Notes\nReview LO1."
    result = ExportRenderer().prepare_content(markdown, ExportAudience.STUDENT_COPY)
    assert "What is IoT?" in result
    assert "Internet of Things" not in result
    assert "Lecturer Notes" not in result


def test_student_copy_removes_inline_answer_disclosures() -> None:
    markdown = "# Quiz\n1. What is IoT? [Answer: Internet of Things]\nAnswer: Internet of Things\n2. Name a sensor."
    result = ExportRenderer().prepare_content(markdown, ExportAudience.STUDENT_COPY)
    assert "Internet of Things" not in result
    assert "What is IoT?" in result
    assert "Name a sensor" in result


@pytest.mark.parametrize(
    ("format_name", "signature"),
    [
        (ExportFormat.MARKDOWN, b"#"),
        (ExportFormat.HTML, b"<!doctype html>"),
        (ExportFormat.DOCX, b"PK"),
        (ExportFormat.PDF, b"%PDF"),
        (ExportFormat.PPTX, b"PK"),
        (ExportFormat.XLSX, b"PK"),
    ],
)
def test_export_renderer_creates_supported_formats(format_name: ExportFormat, signature: bytes) -> None:
    rendered = ExportRenderer().render(
        title="IoT Practical",
        markdown="# IoT Practical\n## Outcomes\n- Connect a sensor\n## Procedure\n1. Wire the sensor.",
        export_format=format_name,
        audience=ExportAudience.LECTURER_PACK,
    )
    assert rendered.content.startswith(signature)
    assert len(rendered.content) > 20
    if format_name in {ExportFormat.DOCX, ExportFormat.PPTX, ExportFormat.XLSX}:
        assert zipfile.is_zipfile(io.BytesIO(rendered.content))


def test_output_workflow_builds_structured_sections_and_quality_gates() -> None:
    structured = TeachingOutputWorkflow().structure(
        task_type=TeachingTaskType.PRACTICAL_LESSON,
        markdown=(
            "# IoT Sensor Practical\n## Learning Outcomes\nConnect a sensor.\n"
            "## Equipment\n- Sensor\n## Safety\nPower off before wiring.\n"
            "## Procedure\n1. Wire the sensor.\n## Assessment\nDemonstrate a reading."
        ),
        classification={"detected_entities": {"duration": "2 hours"}},
        module_context={"module_code": "IOT101"},
    )
    assert structured["blueprint_id"] == "practical-lesson-1.0"
    assert structured["missing_required_sections"] == []
    assert structured["module_context"]["module_code"] == "IOT101"


def test_classifier_marks_all_assessment_outputs_for_human_review() -> None:
    classifier = TeachingTaskClassifier()
    for prompt in (
        "Create a quiz on IoT",
        "Generate a 50-mark test",
        "Make an assignment brief",
        "Create an analytic rubric",
        "Write a marking guide",
    ):
        assert classifier.classify(prompt).human_review_required is True


def test_prompt_contains_authorised_module_context_and_release_rule() -> None:
    classification = TeachingTaskClassifier().classify("Create a test")
    prompt = PromptBuilder().build_system_prompt(
        classification=classification,
        user_role="lecturer",
        sources=[],
        module_context="Module: IOT101 — Introduction to Internet of Things\nLearning outcomes:\n- LO1: Explain IoT.",
    )
    assert "AUTHORISED MODULE CONTEXT" in prompt
    assert "IOT101" in prompt
    assert "student-facing copy must never contain an answer key" in prompt


def test_v17_api_routes_are_registered_before_dynamic_output_route() -> None:
    # app.openapi() flattens all included routers correctly in FastAPI >= 0.95
    paths = list(app.openapi()["paths"].keys())
    download = paths.index("/api/v1/teaching-outputs/exports/{export_id}/download")
    dynamic = paths.index("/api/v1/teaching-outputs/{output_id}")
    assert download < dynamic
    assert "/api/v1/teaching-contexts" in paths
    assert "/api/v1/teaching-outputs/{output_id}/workflow" in paths


def test_role_catalogue_contains_independent_output_permissions() -> None:
    catalogue = json.loads(
        Path("services/database/seeds/role_permissions.json").read_text(encoding="utf-8")
    )
    permissions = {item["code"] for item in catalogue["permissions"]}
    assert {"outputs.edit", "outputs.review", "outputs.approve", "outputs.release"}.issubset(permissions)
    roles = {item["code"]: set(item["permissions"]) for item in catalogue["roles"]}
    assert "outputs.approve" not in roles["institution_administrator"]
    assert "outputs.approve" in roles["head_of_department"]
    assert "outputs.review" in roles["external_moderator"]
    assert "outputs.edit" not in roles["external_reviewer"]


def test_export_filename_is_safe_and_bounded() -> None:
    name = safe_export_filename("IoT / Sensor: Practical? *Draft*", "docx")
    assert name.endswith(".docx")
    assert "/" not in name and ":" not in name and "?" not in name
