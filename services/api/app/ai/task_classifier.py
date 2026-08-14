from __future__ import annotations

import re

from .contracts import PrivacyClass, TaskClassification, TeachingTaskType


class TeachingTaskClassifier:
    """Deterministic, explainable first-pass classifier.

    A later evaluated model may assist ambiguous classification, but this rule
    layer remains the auditable baseline and never exposes provider reasoning.
    """

    VERSION = "rules-1.1"

    _patterns: list[tuple[TeachingTaskType, tuple[str, ...]]] = [
        (TeachingTaskType.PRACTICAL_LESSON, ("practical lesson", "lab lesson", "laboratory lesson", "workshop lesson")),
        (TeachingTaskType.LESSON_PLAN, ("lesson plan", "teaching plan", "lecture plan", "2-hour lesson", "two-hour lesson")),
        (TeachingTaskType.MARKING_GUIDE, ("marking guide", "marking memo", "memorandum", "model answer")),
        (TeachingTaskType.RUBRIC, ("rubric", "assessment criteria", "grading criteria")),
        (TeachingTaskType.CASE_STUDY, ("case study", "scenario-based activity", "problem scenario")),
        (TeachingTaskType.MODERATION_REVIEW, ("moderate", "moderation", "external examiner", "review this assessment")),
        (TeachingTaskType.ALIGNMENT_REVIEW, ("alignment", "learning outcome mapping", "constructive alignment", "map outcomes")),
        (TeachingTaskType.EXAMINATION, ("examination", "exam paper", "final exam")),
        (TeachingTaskType.ASSIGNMENT, ("assignment", "project brief", "coursework")),
        (TeachingTaskType.QUIZ, ("quiz", "multiple choice questions", "mcq")),
        (TeachingTaskType.TEST, ("test", "class test", "assessment paper")),
        (TeachingTaskType.TUTORIAL, ("tutorial", "worksheet", "practice questions")),
        (TeachingTaskType.DEPARTMENTAL_ANALYSIS, ("department overview", "lecturer workload", "departmental teaching", "module readiness")),
    ]

    _source_triggers = (
        "source", "citation", "reference", "latest", "current", "evidence", "research",
        "policy", "standard", "regulation", "statistics", "according to", "published",
    )
    _institution_triggers = (
        "our institution", "institutional", "faculty policy", "department policy", "module guide",
        "study guide", "uploaded", "attached", "our template", "our curriculum",
        # SA HE authoritative knowledge topics — always search the corpus
        "nqf", "heqsf", "saqa", "dhet", " che ", "council on higher education",
        "notional learning", "nqf credit", "nqf level", "accreditation",
        "higher education act", "recognition of prior learning", "rpl",
        "academic workload", "lecturer workload", "moderation policy",
        "assessment policy", "academic integrity", "plagiarism policy",
        "programme approval", "qualification framework", "credit framework",
    )
    _restricted_triggers = (
        "confidential exam", "unreleased exam", "restricted assessment", "student marks",
        "student records", "moderation report", "external moderation",
    )
    _human_review_types = {
        TeachingTaskType.QUIZ,
        TeachingTaskType.TEST,
        TeachingTaskType.ASSIGNMENT,
        TeachingTaskType.EXAMINATION,
        TeachingTaskType.RUBRIC,
        TeachingTaskType.MARKING_GUIDE,
        TeachingTaskType.MODERATION_REVIEW,
        TeachingTaskType.ALIGNMENT_REVIEW,
    }

    def classify(self, text: str, *, has_attachments: bool = False) -> TaskClassification:
        normalized = re.sub(r"\s+", " ", text.strip().lower())
        matched_type = TeachingTaskType.GENERIC_ANSWER
        matched_phrase: str | None = None
        for task_type, phrases in self._patterns:
            for phrase in phrases:
                if phrase in normalized:
                    matched_type = task_type
                    matched_phrase = phrase
                    break
            if matched_phrase:
                break

        source_required = any(trigger in normalized for trigger in self._source_triggers)
        institution_required = has_attachments or any(
            trigger in normalized for trigger in self._institution_triggers
        )
        restricted = any(trigger in normalized for trigger in self._restricted_triggers)
        privacy = (
            PrivacyClass.RESTRICTED_ASSESSMENT
            if restricted
            else PrivacyClass.CONFIDENTIAL
            if "confidential" in normalized
            else PrivacyClass.INTERNAL
        )
        entities: dict[str, str | int] = {}
        duration = re.search(r"\b(\d+(?:\.\d+)?)\s*[-–—]?\s*(hour|hours|minute|minutes)\b", normalized)
        if duration:
            entities["duration"] = f"{duration.group(1)} {duration.group(2)}"
        level = re.search(
            r"\b(diploma|certificate|undergraduate|postgraduate|master(?:'s)?|doctoral|phd|nqf\s*\d+)\b",
            normalized,
        )
        if level:
            entities["academic_level"] = level.group(1)
        marks = re.search(r"\b(\d{1,3})\s*[-–—]?\s*marks?\b", normalized)
        if marks:
            entities["total_marks"] = int(marks.group(1))

        rationale = [f"matched:{matched_phrase}" if matched_phrase else "fallback:generic"]
        if source_required:
            rationale.append("sources:explicit_or_factual_trigger")
        if institution_required:
            rationale.append("context:institution_or_attachment")
        if restricted:
            rationale.append("privacy:restricted_trigger")

        return TaskClassification(
            task_type=matched_type,
            confidence=0.94 if matched_phrase else 0.62,
            source_verification_required=source_required,
            institutional_context_required=institution_required,
            human_review_required=matched_type in self._human_review_types,
            privacy_classification=privacy,
            detected_entities=entities,
            rationale_codes=rationale,
        )
