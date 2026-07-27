# Ollama Windows Setup

## Purpose

This guide installs Ollama and pulls approved development candidates on Windows using project-managed PowerShell scripts.

## Prerequisites

- Windows 10 or later;
- sufficient free disk for the selected profile;
- permission to install software;
- internet access for the initial model pull;
- current GPU drivers where acceleration is expected.

## Recommended command

From the repository root in PowerShell:

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\scripts\development\Setup-Local-AI.ps1 -Profile standard -SkipExisting -SmokeTest
```

Profiles:

```powershell
.\scripts\development\Setup-Local-AI.ps1 -Profile minimal
.\scripts\development\Setup-Local-AI.ps1 -Profile standard
.\scripts\development\Setup-Local-AI.ps1 -Profile advanced
```

Custom pull:

```powershell
.\scripts\development\Install-Ollama-Windows.ps1
.\scripts\development\Pull-Ollama-Models.ps1 -Profile custom -Models 'qwen3:4b-instruct','gemma3:4b'
```

## Direct official installation command

The official Ollama Windows page currently documents:

```powershell
irm https://ollama.com/install.ps1 | iex
```

The project wrapper performs the same official installation path with checks and then verifies `ollama --version`.

## Verification

```powershell
ollama --version
ollama list
Invoke-RestMethod http://localhost:11434/api/tags
.\scripts\development\Test-AI-Providers.ps1
```

## Important

Model binaries are intentionally not stored in Git or bundled in the project ZIP. They are large, operating-environment-specific, updated independently and may have separate licence terms. Pull them on the target computer and record the local inventory.
