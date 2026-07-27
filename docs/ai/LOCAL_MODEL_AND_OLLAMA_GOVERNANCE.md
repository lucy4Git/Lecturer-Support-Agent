# Local Model and Ollama Governance

## Purpose

Ollama provides a practical local inference path for development, offline operation, privacy-sensitive tasks and resilience. It does not remove governance obligations.

## Candidate profiles

The authoritative machine-readable profiles are in `config/ai/ollama-model-profiles.json`.

- **Minimal:** Qwen 3 4B Instruct and multilingual embeddings.
- **Standard:** Qwen 3 8B, DeepSeek-R1 8B, Gemma 3 4B and multilingual embeddings.
- **Advanced:** larger Qwen, DeepSeek-R1 and Gemma candidates plus embedding benchmarks.

The standard profile is a development recommendation, not a promise that every computer can run all models efficiently.

## Approval checklist

Before production use, record:

- model source and immutable digest;
- licence and use restrictions;
- parameter/quantisation variant;
- host, CPU, GPU, RAM, VRAM and disk requirements;
- supported modalities and tools;
- benchmark results by discipline and task;
- hallucination and fabricated-citation results;
- unsafe laboratory/clinical instruction results;
- multilingual and accessibility results;
- patch and retirement plan.

## Security

- Bind Ollama only to approved interfaces; do not expose port 11434 publicly.
- Use host firewalls and service accounts.
- Encrypt disks that hold models, prompts, caches or institutional material.
- Separate development and production hosts.
- Do not write sensitive prompts to unrestricted logs.
- Scan model and Modelfile provenance before use.
- Record all model pulls and upgrades.

## Quality boundary

A local model may draft, classify or assist, but it must pass the same validators as a cloud model. It may not fabricate sources or claim institutional compliance. High-stakes content remains human-reviewed.

## Installation

Use the PowerShell scripts in `scripts/development/`:

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\scripts\development\Setup-Local-AI.ps1 -Profile standard -SkipExisting -SmokeTest
```

The script installs Ollama through the official Windows installer when required, pulls the selected profile without deleting existing models, and writes a local model inventory under `runtime/model-inventory/`.
