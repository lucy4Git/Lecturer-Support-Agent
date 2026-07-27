# Validation Status — v2.5

## Current truth

All cumulative functional foundations from v1.1 through v2.5 are implemented in source and pass the available static/unit checks. Runtime, institutional interoperability, deployment, legal approval and pilot claims remain unverified until evidence is produced.

## v2.5 additions awaiting runtime proof

- Alembic migration `20260726_0011`, all 124 SQLAlchemy tables, tenant RLS and restricted database-role grants.
- Password reset, email verification, SMTP delivery, TOTP MFA, recovery-code use and session revocation.
- OIDC provider discovery, JWKS validation, PKCE/state/nonce, redirect allowlists and federated account linking.
- Canvas, Moodle and OneRoster connectivity, pagination, retry, staging, mappings and canonical adoption controls.
- Legal holds, second approval and supported physical deletion across PostgreSQL, object versions and Qdrant.
- PostgreSQL/object-storage/Qdrant tenant backup, SHA-256 manifests, encryption-at-rest attestation and isolated restore evidence.
- OpenAlex/Crossref metadata acquisition, PWA install/offline behaviour, accessibility, performance and pilot evaluation.

## Explicit boundaries

- Secret values remain in `.env` or a production secret manager and are not included in the repository.
- Integration syncs stage external records; they do not silently overwrite canonical institutional data.
- Claim verification establishes retrieval/citation coverage but does not claim semantic entailment.
- Real third-party full text is not bundled without item-level rights and intended-use approval.
- Legal/commercial documents are templates pending qualified review.
- A restore drill without an approved isolated restore executable is reported as `manifest_and_catalogue_validated`, not as a completed restoration.

## Release gate

The project may be labelled `validated_on_owner_machine` only after full migration/RLS, services, account security, integration, deletion, backup/restore, AI, PWA/browser, accessibility, security, performance and role-based workflow evidence passes and all critical/high findings are closed.

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\scripts\validation\Invoke-ConsolidatedOwnerValidation.ps1 `
  -Mode full `
  -InstallDependencies `
  -StartInfrastructure `
  -RunLivePreview
```

The command never launches Docker Desktop. Start Docker Desktop manually.
