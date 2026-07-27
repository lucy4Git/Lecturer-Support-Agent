from __future__ import annotations

import re
from dataclasses import dataclass

from fastapi import HTTPException, status

from services.database.models.enums import AssessmentRiskLevel, SafetyReviewStatus

from ..ai.contracts import TeachingTaskType


ASSESSMENT_TYPES = {
    TeachingTaskType.QUIZ,
    TeachingTaskType.TEST,
    TeachingTaskType.ASSIGNMENT,
    TeachingTaskType.EXAMINATION,
    TeachingTaskType.RUBRIC,
    TeachingTaskType.MARKING_GUIDE,
    TeachingTaskType.MODERATION_REVIEW,
    TeachingTaskType.ALIGNMENT_REVIEW,
}

GENERATION_ROLES = {
    "lecturer",
    "module_coordinator",
    "programme_coordinator",
    "head_of_department",
}


@dataclass(frozen=True, slots=True)
class SafetyFinding:
    code: str
    status: str
    message: str

    def as_dict(self) -> dict[str, str]:
        return {"code": self.code, "status": self.status, "message": self.message}


@dataclass(frozen=True, slots=True)
class SafetyEvaluation:
    status: SafetyReviewStatus
    risk_level: AssessmentRiskLevel
    checks: list[dict[str, str]]
    warnings: list[str]
    blocked_reasons: list[str]
    answers_detected: bool
    personal_data_detected: bool
    student_copy_safe: bool


class AssessmentSafetyEvaluator:
    """Deterministic assessment guard used before and after generation.

    It does not claim pedagogical approval. It prevents clearly unsafe role use,
    detects likely answer material and personal data, checks mark totals where
    possible, and creates an auditable human-review gate.
    """

    VERSION = "assessment-safety-1.0"
    _answer_patterns = re.compile(
        r"^#{1,6}\s*(answer|answers|answer key|marking guide|memorandum|model answer)s?\b|"
        r"^\s*(answer|solution)\s*:\s*",
        re.IGNORECASE | re.MULTILINE,
    )
    _personal_patterns = re.compile(
        r"(?i)\b(?:student(?:\s+number|\s+id)?|learner(?:\s+number|\s+id)?)\s*[:#-]\s*[A-Z0-9]{5,}\b|"
        r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b",
        re.IGNORECASE,
    )
    _mark_pattern = re.compile(r"(?i)(?:\[|\(|\b)(\d{1,3})\s*marks?(?:\]|\)|\b)")

    def enforce_generation_role(self, task_type: TeachingTaskType, role_code: str) -> None:
        if task_type in ASSESSMENT_TYPES and task_type not in {
            TeachingTaskType.MODERATION_REVIEW,
            TeachingTaskType.ALIGNMENT_REVIEW,
        } and role_code not in GENERATION_ROLES:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=(
                    "The active role may review assigned assessment material but may not generate "
                    "a new assessment artifact."
                ),
            )

    def risk_for(self, task_type: TeachingTaskType) -> AssessmentRiskLevel:
        if task_type in {TeachingTaskType.EXAMINATION, TeachingTaskType.MARKING_GUIDE}:
            return AssessmentRiskLevel.HIGH
        if task_type in {
            TeachingTaskType.TEST,
            TeachingTaskType.ASSIGNMENT,
            TeachingTaskType.RUBRIC,
            TeachingTaskType.MODERATION_REVIEW,
            TeachingTaskType.ALIGNMENT_REVIEW,
        }:
            return AssessmentRiskLevel.MEDIUM
        if task_type == TeachingTaskType.QUIZ:
            return AssessmentRiskLevel.LOW
        return AssessmentRiskLevel.NONE

    def evaluate(
        self,
        *,
        task_type: TeachingTaskType,
        content: str,
        detected_total_marks: int | None,
        module_context_available: bool,
    ) -> SafetyEvaluation:
        risk = self.risk_for(task_type)
        checks: list[SafetyFinding] = []
        warnings: list[str] = []
        blockers: list[str] = []
        answers = bool(self._answer_patterns.search(content))
        personal = bool(self._personal_patterns.search(content))

        if personal:
            blockers.append(
                "Potential personal or student-identifying data was detected in the generated output."
            )
            checks.append(SafetyFinding("personal_data", "blocked", blockers[-1]))
        else:
            checks.append(SafetyFinding("personal_data", "passed", "No obvious personal data pattern was detected."))

        if risk in {AssessmentRiskLevel.HIGH, AssessmentRiskLevel.MEDIUM}:
            if module_context_available:
                checks.append(SafetyFinding("module_context", "passed", "Authorised module context was attached."))
            else:
                warning = (
                    "No authorised module context was selected. Outcome and level alignment must be "
                    "confirmed by the responsible academic before use."
                )
                warnings.append(warning)
                checks.append(SafetyFinding("module_context", "warning", warning))

        if task_type in ASSESSMENT_TYPES:
            checks.append(
                SafetyFinding(
                    "human_approval",
                    "required",
                    "The artifact remains an AI-generated draft until an authorised human completes the workflow.",
                )
            )

        mark_values = [int(value) for value in self._mark_pattern.findall(content)]
        if detected_total_marks is not None and mark_values:
            summed = sum(value for value in mark_values if value <= detected_total_marks)
            # Headings and repeated mark summaries can duplicate totals, so only
            # flag an obvious shortage; exact validation remains a human check.
            if summed < detected_total_marks:
                warning = (
                    f"Detected item marks total approximately {summed}, below the requested "
                    f"{detected_total_marks} marks. Verify the allocation."
                )
                warnings.append(warning)
                checks.append(SafetyFinding("mark_allocation", "warning", warning))
            else:
                checks.append(SafetyFinding("mark_allocation", "passed", "A plausible mark allocation was detected."))
        elif detected_total_marks is not None:
            warning = "A total mark requirement was detected, but item-level marks could not be verified automatically."
            warnings.append(warning)
            checks.append(SafetyFinding("mark_allocation", "warning", warning))

        if answers:
            checks.append(SafetyFinding("answer_separation", "required", "Answer or marking content was detected and must be excluded from student copies."))
        elif task_type in {TeachingTaskType.QUIZ, TeachingTaskType.TEST, TeachingTaskType.EXAMINATION}:
            warning = "No clearly separated answer key was detected; lecturer-pack completeness should be reviewed."
            warnings.append(warning)
            checks.append(SafetyFinding("answer_separation", "warning", warning))

        if blockers:
            status_value = SafetyReviewStatus.BLOCKED
        elif risk != AssessmentRiskLevel.NONE or warnings:
            status_value = SafetyReviewStatus.REQUIRES_REVIEW
        else:
            status_value = SafetyReviewStatus.PASSED

        return SafetyEvaluation(
            status=status_value,
            risk_level=risk,
            checks=[item.as_dict() for item in checks],
            warnings=warnings,
            blocked_reasons=blockers,
            answers_detected=answers,
            personal_data_detected=personal,
            student_copy_safe=not personal and not answers,
        )
