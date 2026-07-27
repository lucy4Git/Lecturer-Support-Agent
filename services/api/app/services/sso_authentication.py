from __future__ import annotations

from datetime import datetime, timedelta, timezone
import secrets
from uuid import UUID, uuid4

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from services.database.models import (
    AccountChallenge, FederatedIdentity, Institution, Membership, SSOConnection, User,
)

from ..core.database import set_auth_tenant_context
from ..core.security import TokenService
from ..core.sensitive_content import SensitiveContentProtector
from ..core.settings import Settings, get_settings
from ..integrations.oidc import OIDCClient, pkce_pair
from ..schemas.auth import TokenResponse
from ..schemas.completion import SSOCallbackResponse, SSOExchangeRequest, SSOStartRequest, SSOStartResponse
from .authentication import AuthenticationService


class SSOAuthenticationService:
    def __init__(self, session: AsyncSession, settings: Settings | None = None) -> None:
        self.session = session
        self.settings = settings or get_settings()
        self.tokens = TokenService(self.settings)
        self.auth = AuthenticationService(session, self.settings)
        self.protector = SensitiveContentProtector(self.settings)

    async def start(self, payload: SSOStartRequest) -> SSOStartResponse:
        institution = await self._institution(payload.institution_id, payload.institution_slug)
        await set_auth_tenant_context(self.session, str(institution.id))
        connection = await self.session.scalar(select(SSOConnection).where(
            SSOConnection.tenant_id == institution.id,
            SSOConnection.code == payload.connection_code,
            SSOConnection.is_enabled.is_(True),
            SSOConnection.protocol == "oidc",
        ))
        if connection is None:
            raise HTTPException(status_code=404, detail="The OIDC connection is not available.")
        if not self._redirect_allowed(connection, payload.redirect_uri):
            raise HTTPException(status_code=400, detail="The requested OIDC redirect URI is not allowlisted.")
        client = OIDCClient(
            issuer_url=connection.issuer_url, client_id=connection.client_id,
            client_secret_reference=connection.client_secret_reference,
            scopes=connection.scopes, settings=self.settings,
        )
        discovery = await client.discover()
        verifier, challenge = pkce_pair()
        nonce = secrets.token_urlsafe(32)
        state_secret = secrets.token_urlsafe(32)
        state = f"{institution.id}.{state_secret}"
        expires = datetime.now(timezone.utc) + timedelta(minutes=self.settings.oidc_state_expiry_minutes)
        record = AccountChallenge(
            id=uuid4(), tenant_id=institution.id, challenge_type="oidc_state",
            token_hash=self.tokens.hash_opaque_token(state), status="pending", expires_at=expires,
            metadata_payload={
                "connection_id": str(connection.id), "redirect_uri": payload.redirect_uri,
                "nonce_ciphertext": self.protector.encrypt(nonce),
                "code_verifier_ciphertext": self.protector.encrypt(verifier),
            },
        )
        self.session.add(record)
        url = client.authorization_url(
            discovery=discovery, redirect_uri=payload.redirect_uri,
            state=state, nonce=nonce, code_challenge=challenge,
        )
        return SSOStartResponse(authorization_url=url, state=state, expires_at=expires)

    async def callback(self, *, state_value: str, code: str) -> SSOCallbackResponse:
        tenant_id = self._tenant_from_opaque(state_value)
        await set_auth_tenant_context(self.session, str(tenant_id))
        now = datetime.now(timezone.utc)
        challenge = await self.session.scalar(select(AccountChallenge).where(
            AccountChallenge.tenant_id == tenant_id,
            AccountChallenge.challenge_type == "oidc_state",
            AccountChallenge.token_hash == self.tokens.hash_opaque_token(state_value),
        ).with_for_update())
        if challenge is None or challenge.status != "pending" or challenge.expires_at <= now:
            raise HTTPException(status_code=401, detail="The OIDC state is invalid or expired.")
        metadata = challenge.metadata_payload
        connection = await self.session.scalar(select(SSOConnection).where(
            SSOConnection.tenant_id == tenant_id,
            SSOConnection.id == UUID(metadata["connection_id"]),
            SSOConnection.is_enabled.is_(True),
        ))
        if connection is None:
            raise HTTPException(status_code=401, detail="The OIDC connection is no longer active.")
        client = OIDCClient(
            issuer_url=connection.issuer_url, client_id=connection.client_id,
            client_secret_reference=connection.client_secret_reference,
            scopes=connection.scopes, settings=self.settings,
        )
        discovery = await client.discover()
        identity = await client.exchange_code(
            discovery=discovery, code=code, redirect_uri=metadata["redirect_uri"],
            code_verifier=self.protector.decrypt(metadata["code_verifier_ciphertext"]),
            expected_nonce=self.protector.decrypt(metadata["nonce_ciphertext"]),
        )
        user = await self._resolve_federated_user(tenant_id, connection, identity)
        membership = await self.session.scalar(select(Membership).where(
            Membership.tenant_id == tenant_id, Membership.user_id == user.id, Membership.status == "active",
        ))
        if membership is None:
            raise HTTPException(status_code=403, detail="The federated account has no active institution membership.")
        roles = await self.auth._active_role_options(tenant_id=tenant_id, user_id=user.id, now=now)
        if not roles:
            raise HTTPException(status_code=403, detail="The federated account has no active role assignment.")
        handoff_secret = secrets.token_urlsafe(32)
        handoff = f"{tenant_id}.{handoff_secret}"
        handoff_expires = now + timedelta(minutes=5)
        self.session.add(AccountChallenge(
            id=uuid4(), tenant_id=tenant_id, user_id=user.id, challenge_type="oidc_handoff",
            token_hash=self.tokens.hash_opaque_token(handoff), status="pending", expires_at=handoff_expires,
            metadata_payload={"membership_id": str(membership.id), "role_codes": [r.role_code for r in roles]},
        ))
        challenge.status = "consumed"; challenge.consumed_at = now
        user.last_login_at = now
        return SSOCallbackResponse(
            handoff_token=handoff,
            available_roles=[role.model_dump(mode="json") for role in roles],
            expires_at=handoff_expires,
        )

    async def exchange(self, payload: SSOExchangeRequest, *, user_agent_hash: str | None, source_ip_hash: str | None) -> TokenResponse:
        raw = payload.handoff_token.get_secret_value()
        tenant_id = self._tenant_from_opaque(raw)
        await set_auth_tenant_context(self.session, str(tenant_id))
        now = datetime.now(timezone.utc)
        challenge = await self.session.scalar(select(AccountChallenge).where(
            AccountChallenge.tenant_id == tenant_id,
            AccountChallenge.challenge_type == "oidc_handoff",
            AccountChallenge.token_hash == self.tokens.hash_opaque_token(raw),
        ).with_for_update())
        if challenge is None or challenge.status != "pending" or challenge.expires_at <= now or challenge.user_id is None:
            raise HTTPException(status_code=401, detail="The OIDC handoff is invalid or expired.")
        membership = await self.session.scalar(select(Membership).where(
            Membership.tenant_id == tenant_id,
            Membership.id == UUID(challenge.metadata_payload["membership_id"]),
            Membership.user_id == challenge.user_id,
            Membership.status == "active",
        ))
        user = await self.session.scalar(select(User).where(User.id == challenge.user_id, User.is_active.is_(True)))
        roles = await self.auth._active_role_options(tenant_id=tenant_id, user_id=challenge.user_id, now=now)
        selected = next((role for role in roles if role.role_code == payload.role_code), None)
        if membership is None or user is None or selected is None:
            raise HTTPException(status_code=403, detail="The requested federated role is unavailable.")
        challenge.status = "consumed"; challenge.consumed_at = now
        return await self.auth._issue_session(
            tenant_id=tenant_id, user=user, membership=membership,
            role_assignment_id=selected.role_assignment_id, role_code=selected.role_code,
            device_label=payload.device_label, user_agent_hash=user_agent_hash,
            source_ip_hash=source_ip_hash, now=now,
        )

    async def _resolve_federated_user(self, tenant_id: UUID, connection: SSOConnection, identity) -> User:
        link = await self.session.scalar(select(FederatedIdentity).where(
            FederatedIdentity.tenant_id == tenant_id,
            FederatedIdentity.sso_connection_id == connection.id,
            FederatedIdentity.external_subject == identity.subject,
        ))
        now = datetime.now(timezone.utc)
        if link is not None:
            link.last_claims = self._safe_claims(identity.claims); link.last_login_at = now
            user = await self.session.scalar(select(User).where(User.id == link.user_id, User.is_active.is_(True)))
            if user is None:
                raise HTTPException(status_code=403, detail="The linked account is inactive.")
            return user
        allow_linking = bool(connection.metadata_payload.get("allow_account_linking_by_verified_email", False))
        if not allow_linking or not identity.email or not identity.email_verified:
            raise HTTPException(status_code=403, detail="The OIDC identity is not linked to an authorised account.")
        user = await self.session.scalar(select(User).where(User.email_normalized == identity.email, User.is_active.is_(True)))
        if user is None:
            raise HTTPException(status_code=403, detail="The verified OIDC email does not match an authorised account.")
        membership = await self.session.scalar(select(Membership).where(
            Membership.tenant_id == tenant_id, Membership.user_id == user.id, Membership.status == "active",
        ))
        if membership is None:
            raise HTTPException(status_code=403, detail="The verified OIDC email has no active institution membership.")
        self.session.add(FederatedIdentity(
            id=uuid4(), tenant_id=tenant_id, user_id=user.id,
            sso_connection_id=connection.id, external_subject=identity.subject,
            external_email=identity.email, last_claims=self._safe_claims(identity.claims), last_login_at=now,
        ))
        return user

    @staticmethod
    def _safe_claims(claims: dict) -> dict:
        allowed = {"sub", "email", "email_verified", "name", "given_name", "family_name", "iss", "aud"}
        return {key: claims[key] for key in allowed if key in claims}

    async def _institution(self, institution_id: UUID | None, institution_slug: str | None) -> Institution:
        statement = select(Institution).where(Institution.is_active.is_(True))
        statement = statement.where(Institution.id == institution_id) if institution_id else statement.where(Institution.slug == institution_slug)
        item = await self.session.scalar(statement)
        if item is None:
            raise HTTPException(status_code=404, detail="Institution was not found or is inactive.")
        return item

    @staticmethod
    def _tenant_from_opaque(value: str) -> UUID:
        try:
            return UUID(value.split(".", 1)[0])
        except (ValueError, IndexError) as exc:
            raise HTTPException(status_code=401, detail="The federated authentication token is malformed.") from exc

    @staticmethod
    def _redirect_allowed(connection: SSOConnection, redirect_uri: str) -> bool:
        allowlist = connection.metadata_payload.get("redirect_uris") or []
        return redirect_uri in allowlist
