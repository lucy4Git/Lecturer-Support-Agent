#!/usr/bin/env python3
from pathlib import Path
import json, re, sys

ROOT = Path(__file__).resolve().parents[2]
REQUIRED = [
    'config/ai/providers.example.json',
    'config/ai/ollama-model-profiles.json',
    'config/ai/model-registry.example.json',
    'data/schemas/ai_provider_registry.schema.json',
    'data/schemas/ollama_model_profiles.schema.json',
    'data/schemas/model_registry.schema.json',
    'scripts/development/Install-Ollama-Windows.ps1',
    'scripts/development/Pull-Ollama-Models.ps1',
    'scripts/development/Setup-Local-AI.ps1',
    'scripts/development/Test-AI-Providers.ps1',
    'docs/ai/MULTI_PROVIDER_MODEL_STRATEGY.md',
    'docs/ai/MODEL_ROUTING_AND_FALLBACK.md',
    'docs/ai/LOCAL_MODEL_AND_OLLAMA_GOVERNANCE.md',
    'docs/architecture/uml/architecture/03_multi_provider_ai_gateway.plantuml',
    'docs/architecture/uml/sequences/11_model_routing_and_fallback.plantuml',
]

errors = []
for rel in REQUIRED:
    p = ROOT / rel
    if not p.exists() or p.stat().st_size == 0:
        errors.append(f'missing or empty: {rel}')

for rel in [
    'config/ai/providers.example.json',
    'config/ai/ollama-model-profiles.json',
    'config/ai/model-registry.example.json',
    'data/schemas/ai_provider_registry.schema.json',
    'data/schemas/ollama_model_profiles.schema.json',
    'data/schemas/model_registry.schema.json',
]:
    try:
        json.loads((ROOT / rel).read_text(encoding='utf-8'))
    except Exception as exc:
        errors.append(f'invalid JSON {rel}: {exc}')

providers = json.loads((ROOT / 'config/ai/providers.example.json').read_text())
ids = {p['id'] for p in providers['providers']}
expected = {'openai', 'anthropic', 'google_gemini', 'deepseek', 'ollama'}
if not expected.issubset(ids):
    errors.append(f'provider registry missing: {sorted(expected - ids)}')

profiles = json.loads((ROOT / 'config/ai/ollama-model-profiles.json').read_text())
for name in ('minimal', 'standard', 'advanced'):
    if name not in profiles['profiles'] or not profiles['profiles'][name]['models']:
        errors.append(f'missing/empty Ollama profile: {name}')

for rel in ['docs/architecture/uml/architecture/03_multi_provider_ai_gateway.plantuml', 'docs/architecture/uml/sequences/11_model_routing_and_fallback.plantuml']:
    text = (ROOT / rel).read_text(encoding='utf-8')
    if text.count('@startuml') != 1 or text.count('@enduml') != 1:
        errors.append(f'PlantUML boundary failure: {rel}')

for rel in ['scripts/development/Install-Ollama-Windows.ps1', 'scripts/development/Pull-Ollama-Models.ps1', 'scripts/development/Setup-Local-AI.ps1', 'scripts/development/Test-AI-Providers.ps1']:
    text = (ROOT / rel).read_text(encoding='utf-8')
    if text.count('{') != text.count('}'):
        errors.append(f'PowerShell brace imbalance: {rel}')
    if 'Set-StrictMode' not in text:
        errors.append(f'PowerShell strict mode missing: {rel}')

if errors:
    print('MULTI-PROVIDER PACK VALIDATION FAILED')
    for err in errors:
        print(f'- {err}')
    sys.exit(1)
print(f'MULTI-PROVIDER PACK VALIDATION PASSED: {len(REQUIRED)} required files, {len(ids)} providers, {len(profiles["profiles"])} Ollama profiles')
