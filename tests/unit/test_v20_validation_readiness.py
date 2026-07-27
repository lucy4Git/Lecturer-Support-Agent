from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_validation_profile_contains_all_runtime_services() -> None:
    profile = json.loads((ROOT / 'config/validation/owner-machine-profile.example.json').read_text())
    assert set(profile['required_services']) == {'postgresql','redis','minio','qdrant','ollama','api','web'}
    assert profile['stop_on_failure'] is False


def test_required_models_cover_generation_and_embeddings() -> None:
    profile = json.loads((ROOT / 'config/validation/owner-machine-profile.example.json').read_text())
    assert 'qwen3:8b' in profile['required_ollama_models']
    assert 'nomic-embed-text-v2-moe' in profile['required_ollama_models']


def test_validation_evidence_is_runtime_only() -> None:
    gitignore = (ROOT / '.gitignore').read_text()
    assert 'runtime/' in gitignore
    orchestrator = (ROOT / 'scripts/validation/Invoke-ConsolidatedOwnerValidation.ps1').read_text()
    assert 'VALIDATION_EVIDENCE_DIR' in orchestrator
    assert 'validation-summary.json' in orchestrator


def test_docker_desktop_is_never_auto_started() -> None:
    orchestrator = (ROOT / 'scripts/validation/Invoke-ConsolidatedOwnerValidation.ps1').read_text().lower()
    prerequisites = (ROOT / 'scripts/validation/Test-OwnerMachinePrerequisites.ps1').read_text().lower()
    assert 'docker desktop' not in orchestrator
    assert 'start docker desktop manually' in prerequisites
