from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

DISCIPLINES = [
    ("engineering", "IoT sensor calibration", "diploma"),
    ("computing", "database normalisation", "undergraduate"),
    ("health_sciences", "infection prevention", "undergraduate"),
    ("education", "formative assessment design", "postgraduate"),
    ("business", "break-even analysis", "diploma"),
    ("law", "case precedent analysis", "undergraduate"),
    ("humanities", "primary-source interpretation", "undergraduate"),
    ("social_sciences", "survey bias", "honours"),
    ("agriculture", "soil moisture management", "diploma"),
    ("arts_design", "visual hierarchy", "undergraduate"),
    ("built_environment", "site risk assessment", "diploma"),
    ("vocational", "electrical fault finding", "certificate"),
]


def record(discipline: str, topic: str, level: str, kind: str) -> dict:
    identifier = f"synthetic-{discipline}-{kind}"
    content = {
        "lesson_plan": {
            "duration_minutes": 90,
            "learning_outcomes": [
                f"Explain the core concepts of {topic}.",
                f"Apply a structured method to a practical {topic} task.",
                "Evaluate evidence and communicate a justified conclusion.",
            ],
            "sequence": [
                {"minutes": 10, "activity": "Diagnostic prompt and prior-knowledge check"},
                {"minutes": 20, "activity": "Lecturer explanation with worked example"},
                {"minutes": 40, "activity": "Guided practical or case-based activity"},
                {"minutes": 15, "activity": "Peer review and feedback"},
                {"minutes": 5, "activity": "Exit ticket"},
            ],
        },
        "assessment": {
            "total_marks": 20,
            "questions": [
                {"prompt": f"Define two important principles in {topic}.", "marks": 4},
                {"prompt": f"Apply the principles to a new {topic} scenario.", "marks": 8},
                {"prompt": "Justify your decision and identify one limitation.", "marks": 8},
            ],
            "human_review_required": True,
            "release_status": "draft",
        },
        "rubric": {
            "criteria": [
                {"name": "Conceptual accuracy", "weight": 35},
                {"name": "Application", "weight": 35},
                {"name": "Evidence and justification", "weight": 20},
                {"name": "Communication", "weight": 10},
            ]
        },
    }[kind]
    digest = hashlib.sha256(json.dumps(content, sort_keys=True).encode()).hexdigest()
    return {
        "record_id": identifier,
        "dataset": "lsa_synthetic_academic_corpus_v2.3",
        "synthetic": True,
        "licence": "Project-generated synthetic fixture; not for academic authority claims",
        "discipline": discipline,
        "topic": topic,
        "qualification_level": level,
        "output_type": kind,
        "language": "en",
        "content": content,
        "sha256": digest,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="data/fixtures/safe/synthetic_academic_corpus_v2.3.jsonl")
    args = parser.parse_args()
    path = Path(args.output)
    path.parent.mkdir(parents=True, exist_ok=True)
    records = [record(*item, kind) for item in DISCIPLINES for kind in ("lesson_plan", "assessment", "rubric")]
    path.write_text("\n".join(json.dumps(item, sort_keys=True) for item in records) + "\n", encoding="utf-8")
    print(f"Wrote {len(records)} synthetic records to {path}")


if __name__ == "__main__":
    main()
