from __future__ import annotations

import base64
import hashlib
import os
import secrets
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlencode

import httpx
import jwt

from ..core.outbound_url import validate_outbound_url
from ..core.settings import Settings, get_settings


@dataclass(frozen=True, slots=True)
class OIDCDiscoveryDocument:
    issuer: str
    authorization_endpoint: str
    token_endpoint: str
    jwks_uri: str
    userinfo_endpoint: str | None


@dataclass(frozen=True, slots=True)
class OIDCIdentity:
    subject: str
    email: str | None
    email_verified: bool
    given_name: str | None
    family_name: str | None
    display_name: str | None
    claims: dict[str, Any]


def pkce_pair() -> tuple[str, str]:
    verifier = base64.urlsafe_b64encode(secrets.token_bytes(48)).decode("ascii").rstrip("=")
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode("ascii")).digest()).decode("ascii").rstrip("=")
    return verifier, challenge


class OIDCClient:
    """Standards-oriented OIDC Authorization Code + PKCE client.

    Secrets are read only from the configured environment-variable reference.
    Discovery and JWKS documents are retrieved from the configured issuer and
    ID-token issuer, audience, signature, expiry, and nonce are verified.
    """

    def __init__(self, *, issuer_url: str, client_id: str, client_secret_reference: str | None,
                 scopes: list[str], settings: Settings | None = None,
                 client: httpx.AsyncClient | None = None) -> None:
        self.settings = settings or get_settings()
        validate_outbound_url(issuer_url, self.settings, purpose="OIDC issuer")
        self.issuer_url = issuer_url.rstrip("/")
        self.client_id = client_id
        self.client_secret_reference = client_secret_reference
        self.scopes = scopes or ["openid", "profile", "email"]
        self._client = client

    async def discover(self) -> OIDCDiscoveryDocument:
        owns = self._client is None
        client = self._client or httpx.AsyncClient(timeout=self.settings.oidc_http_timeout_seconds, follow_redirects=False)
        try:
            response = await client.get(f"{self.issuer_url}/.well-known/openid-configuration")
            response.raise_for_status()
            payload = response.json()
        finally:
            if owns:
                await client.aclose()
        issuer = str(payload.get("issuer") or "").rstrip("/")
        if issuer != self.issuer_url:
            raise RuntimeError("OIDC discovery issuer does not match the configured issuer.")
        required = ["authorization_endpoint", "token_endpoint", "jwks_uri"]
        if any(not payload.get(field) for field in required):
            raise RuntimeError("OIDC discovery document is incomplete.")
        for field in required:
            validate_outbound_url(str(payload[field]), self.settings, purpose=f"OIDC {field}")
        if payload.get("userinfo_endpoint"):
            validate_outbound_url(str(payload["userinfo_endpoint"]), self.settings, purpose="OIDC userinfo endpoint")
        return OIDCDiscoveryDocument(
            issuer=issuer,
            authorization_endpoint=str(payload["authorization_endpoint"]),
            token_endpoint=str(payload["token_endpoint"]),
            jwks_uri=str(payload["jwks_uri"]),
            userinfo_endpoint=str(payload["userinfo_endpoint"]) if payload.get("userinfo_endpoint") else None,
        )

    def authorization_url(self, *, discovery: OIDCDiscoveryDocument, redirect_uri: str,
                          state: str, nonce: str, code_challenge: str) -> str:
        params = {
            "client_id": self.client_id,
            "response_type": "code",
            "redirect_uri": redirect_uri,
            "scope": " ".join(self.scopes),
            "state": state,
            "nonce": nonce,
            "code_challenge": code_challenge,
            "code_challenge_method": "S256",
        }
        return f"{discovery.authorization_endpoint}?{urlencode(params)}"

    async def exchange_code(self, *, discovery: OIDCDiscoveryDocument, code: str,
                            redirect_uri: str, code_verifier: str, expected_nonce: str) -> OIDCIdentity:
        data = {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": redirect_uri,
            "client_id": self.client_id,
            "code_verifier": code_verifier,
        }
        if self.client_secret_reference:
            secret = os.getenv(self.client_secret_reference)
            if not secret:
                raise RuntimeError(f"OIDC secret reference {self.client_secret_reference} is not configured.")
            data["client_secret"] = secret
        owns = self._client is None
        client = self._client or httpx.AsyncClient(timeout=self.settings.oidc_http_timeout_seconds, follow_redirects=False)
        try:
            token_response = await client.post(discovery.token_endpoint, data=data, headers={"Accept": "application/json"})
            token_response.raise_for_status()
            token_payload = token_response.json()
            id_token = str(token_payload.get("id_token") or "")
            if not id_token:
                raise RuntimeError("The OIDC provider did not return an ID token.")
            jwks_response = await client.get(discovery.jwks_uri)
            jwks_response.raise_for_status()
            jwks = jwks_response.json()
        finally:
            if owns:
                await client.aclose()
        claims = self._decode_id_token(id_token, discovery=discovery, jwks=jwks)
        if not secrets.compare_digest(str(claims.get("nonce") or ""), expected_nonce):
            raise RuntimeError("OIDC nonce verification failed.")
        subject = str(claims.get("sub") or "").strip()
        if not subject:
            raise RuntimeError("OIDC ID token does not contain a subject.")
        return OIDCIdentity(
            subject=subject,
            email=str(claims.get("email") or "").strip().lower() or None,
            email_verified=bool(claims.get("email_verified")),
            given_name=str(claims.get("given_name") or "").strip() or None,
            family_name=str(claims.get("family_name") or "").strip() or None,
            display_name=str(claims.get("name") or "").strip() or None,
            claims=claims,
        )

    def _decode_id_token(self, token: str, *, discovery: OIDCDiscoveryDocument, jwks: dict[str, Any]) -> dict[str, Any]:
        header = jwt.get_unverified_header(token)
        kid = header.get("kid")
        algorithm = str(header.get("alg") or "")
        if algorithm not in {"RS256", "RS384", "RS512", "ES256", "ES384", "ES512"}:
            raise RuntimeError("The OIDC ID-token signing algorithm is not permitted.")
        keys = jwks.get("keys") or []
        selected = next((key for key in keys if key.get("kid") == kid), None)
        if selected is None:
            raise RuntimeError("The OIDC signing key was not found in the provider JWKS.")
        public_key = jwt.PyJWK.from_dict(selected, algorithm=algorithm).key
        return jwt.decode(
            token,
            key=public_key,
            algorithms=[algorithm],
            audience=self.client_id,
            issuer=discovery.issuer,
            options={"require": ["exp", "iat", "iss", "aud", "sub", "nonce"]},
            leeway=30,
        )
