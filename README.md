# Lecturer Support Agent

A standalone, commercial-ready, AI-native platform for lecturers and authorised teaching-and-learning stakeholders across any higher education institution, academic discipline, organisational structure, and modern device.

## Product vision

The platform provides **one unified ChatGPT-style work area**. Users request any authorised teaching-and-learning task in natural language. The system decides whether to produce a lesson plan, quiz, test, rubric, marking guide, examination, case study, practical exercise, alignment review, moderation record, departmental analysis, or another suitable inline artifact. Users never choose models, agents, workflows, or separate artifact workspaces.

Generic assistance is the default. Institutional context is used only when relevant and available. Any displayed source must be genuine and traceable; fabricated citations, policies, links, approval states, and compliance claims are prohibited.

## Non-negotiable decisions

1. Standalone lecturer-support scope; never merge with AcademicOS/AIS, AQAA, RIAE, PersonalOS, or another project.
2. One unified work area; no separate lesson-plan, rubric, test, report, moderation, or artifact workspace.
3. Support every academic discipline, pedagogy, qualification level, delivery mode, and assessment approach.
4. Multi-institutional and configurable for any HEI structure and terminology.
5. Responsive web/PWA first, usable on desktop, laptop, tablet, and mobile; architecture ready for native clients.
6. Institution Administrator and Head of Department are independent roles.
7. Bulk upload is a contextual permission-based button for any authorised role that needs it.
8. Uploads never overwrite existing material; every item is stored as an immutable version with time, date, user, role, batch, checksum, scope, and provenance.
9. Human users retain formal teaching, moderation, approval, and governance authority.
10. Security, accessibility, auditability, live-preview testing, observability, and commercial UX are release requirements.

## Primary roles

- Lecturer
- Module or Programme Coordinator
- Head of Department
- Institution Administrator
- Internal Moderator
- External Moderator
- External Reviewer
- Platform Operator, limited to technical SaaS operations

## Repository map

| Path | Purpose |
|---|---|
| `apps/` | Responsive web/PWA and future mobile client |
| `services/` | Backend and AI service boundaries |
| `packages/` | Shared UI, schemas, prompts, SDKs, and contracts |
| `docs/` | Blueprint, requirements, architecture, PlantUML, UX, security, testing, research, and operations |
| `infrastructure/` | Containers, Kubernetes, IaC, observability, gateways, and secrets |
| `data/` | Migrations, schemas, manifests, safe fixtures, and evaluation metadata |
| `tests/` | Unit, contract, integration, E2E, security, performance, accessibility, recovery, and AI evaluation |
| `scripts/` | Development, validation, migration, diagram, and release automation |

## Mandatory reading before implementation

1. `PROJECT_CONSTITUTION.md`
2. `docs/blueprints/LECTURER_SUPPORT_AGENT_MASTER_BLUEPRINT.md`
3. `docs/requirements/FUNCTIONAL_REQUIREMENTS.md`
4. `docs/requirements/ROLE_PERMISSION_MATRIX.md`
5. `docs/architecture/SYSTEM_ARCHITECTURE.md`
6. `docs/data/CONTENT_VERSIONING_AND_PROVENANCE.md`
7. `docs/ux/UNIFIED_AI_WORK_AREA.md`
8. `CLAUDE.md`


## Multi-provider AI and local Ollama setup

The platform is not limited to OpenAI. Its governed model fabric supports OpenAI, Anthropic Claude, Google Gemini, DeepSeek API and local Ollama models. Users remain in one unified work area while the gateway selects an approved model.

On Windows, install Ollama and pull the standard development profile from the repository root:

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\scripts\development\Setup-Local-AI.ps1 -Profile standard -SkipExisting -SmokeTest
```

Model binaries are not bundled in the ZIP or Git repository. See `docs/operations/OLLAMA_WINDOWS_SETUP.md` and `docs/ai/MULTI_PROVIDER_MODEL_STRATEGY.md`.

## Current implementation checkpoint: v2.5

v2.5 closes the implementable commercial gaps before live institutional deployment: password recovery, email verification, TOTP MFA, OIDC SSO, Canvas/Moodle/OneRoster integration contracts, staged synchronisation, legal holds and governed deletion, connected tenant-scoped backup/restore-drill handlers, real-data rights gates, feedback/evaluation capture, PWA foundations, and commercial/legal/pilot packages.

No real provider credentials, institutional secrets, copyrighted full-text corpus, or production evidence is bundled. Runtime-dependent behaviour remains owner-machine and institutional acceptance validation pending.

```powershell
.\scripts\validation\Validate-V2.5.ps1 -RunTests
```
