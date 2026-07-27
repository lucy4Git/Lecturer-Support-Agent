from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from ..ai.contracts import TeachingTaskType


@dataclass(frozen=True, slots=True)
class OutputBlueprint:
    blueprint_id: str
    required_sections: tuple[str, ...]
    recommended_sections: tuple[str, ...] = ()


BLUEPRINTS: dict[TeachingTaskType, OutputBlueprint] = {
    TeachingTaskType.LESSON_PLAN: OutputBlueprint(
        "lesson-plan-1.0",
        ("learning outcomes", "resources", "lesson sequence", "assessment", "reflection"),
        ("differentiation", "preparation"),
    ),
    TeachingTaskType.PRACTICAL_LESSON: OutputBlueprint(
        "practical-lesson-1.0",
        ("learning outcomes", "equipment", "safety", "procedure", "assessment"),
        ("troubleshooting", "reflection"),
    ),
    TeachingTaskType.QUIZ: OutputBlueprint("quiz-1.0", ("instructions", "questions", "answer key")),
    TeachingTaskType.TEST: OutputBlueprint("test-1.0", ("instructions", "questions", "marking guide")),
    TeachingTaskType.EXAMINATION: OutputBlueprint(
        "examination-1.0", ("instructions", "questions", "marking guide", "quality checks")
    ),
    TeachingTaskType.ASSIGNMENT: OutputBlueprint(
        "assignment-1.0", ("purpose", "learning outcomes", "task", "deliverables", "assessment criteria")
    ),
    TeachingTaskType.RUBRIC: OutputBlueprint("rubric-1.0", ("criteria", "performance levels", "scoring guidance")),
    TeachingTaskType.MARKING_GUIDE: OutputBlueprint(
        "marking-guide-1.0", ("mark allocation", "expected responses", "acceptable alternatives", "moderation notes")
    ),
    TeachingTaskType.CASE_STUDY: OutputBlueprint("case-study-1.0", ("case", "learner tasks", "discussion questions", "facilitation notes")),
    TeachingTaskType.TUTORIAL: OutputBlueprint("tutorial-1.0", ("instructions", "activities", "practice tasks", "answer notes")),
    TeachingTaskType.MODERATION_REVIEW: OutputBlueprint("moderation-review-1.0", ("findings", "evidence", "recommendations", "moderator judgement")),
    TeachingTaskType.ALIGNMENT_REVIEW: OutputBlueprint("alignment-review-1.0", ("outcome mapping", "teaching alignment", "assessment alignment", "gaps")),
    TeachingTaskType.DEPARTMENTAL_ANALYSIS: OutputBlueprint("department-analysis-1.0", ("observations", "risks", "priority actions", "follow-up")),
    TeachingTaskType.GENERIC_ANSWER: OutputBlueprint("generic-teaching-output-1.0", ()),
}


class TeachingOutputWorkflow:
    VERSION = "teaching-output-workflow-1.0"
    _heading = re.compile(r"^(#{1,6})\s+(.+?)\s*$")

    def structure(
        self,
        *,
        task_type: TeachingTaskType,
        markdown: str,
        classification: dict[str, Any],
        module_context: dict[str, Any] | None,
    ) -> dict[str, Any]:
        blueprint = BLUEPRINTS[task_type]
        sections: list[dict[str, Any]] = []
        active: dict[str, Any] | None = None
        preamble: list[str] = []
        for line in markdown.splitlines():
            match = self._heading.match(line)
            if match:
                if active is not None:
                    active["content"] = "\n".join(active.pop("lines")).strip()
                    sections.append(active)
                active = {"level": len(match.group(1)), "title": match.group(2).strip(), "lines": []}
            elif active is None:
                preamble.append(line)
            else:
                active["lines"].append(line)
        if active is not None:
            active["content"] = "\n".join(active.pop("lines")).strip()
            sections.append(active)

        headings = [section["title"].lower() for section in sections]
        missing = [
            requirement
            for requirement in blueprint.required_sections
            if not any(requirement in heading or heading in requirement for heading in headings)
        ]
        return {
            "schema_version": "1.0",
            "workflow_version": self.VERSION,
            "blueprint_id": blueprint.blueprint_id,
            "output_type": task_type.value,
            "preamble": "\n".join(preamble).strip(),
            "sections": sections,
            "required_sections": list(blueprint.required_sections),
            "recommended_sections": list(blueprint.recommended_sections),
            "missing_required_sections": missing,
            "quality_warnings": (["Some required production sections were not confidently detected."] if missing else []),
            "classification": classification,
            "module_context": module_context or {},
        }
