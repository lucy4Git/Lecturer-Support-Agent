# Automation Scripts

Development setup, validation, migrations, diagram rendering, fixtures and release checks.

## Local AI on Windows

- `development/Install-Ollama-Windows.ps1` — install/verify Ollama through the official Windows path.
- `development/Pull-Ollama-Models.ps1` — pull a governed profile or custom model list without deleting existing models.
- `development/Setup-Local-AI.ps1` — run installation and profile pull together.
- `development/Test-AI-Providers.ps1` — verify Ollama and report cloud configuration variables.

## Validation

- `validation/validate_data_foundation.py`
- `validation/validate_multi_provider_pack.py`

Implementation must follow `PROJECT_CONSTITUTION.md`, requirements, ADRs and security rules.

## v1.3 database and security scripts

- `database/` starts and stops the manually available Docker stack, runs migrations, creates Qdrant, seeds synthetic tenants, validates RLS and performs deliberate resets.
- `data/` contains the fail-closed approved-dataset acquisition utility.
- `security/New-SafeProjectArchive.ps1` creates a secret-scanned ZIP that excludes `.env`, credentials, runtime secrets and build output.
