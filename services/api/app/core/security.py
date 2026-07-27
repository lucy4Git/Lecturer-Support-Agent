from __future__ import annotations

import hashlib
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID, uuid4

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError
from fastapi import HTTPException, status
from jwt import InvalidTokenError

from .settings import Settings, get_settings


@dataclass(frozen=True, slots=True)
class AccessTokenClaims:
    subject: UUID
    tenant_id: UUID
    membership_id: UUID
    role_assignment_id: UUID
    role_code: str
    session_id: UUID
    token_id: UUID
    expires_at: datetime


class PasswordManager:
    """Argon2id password hashing and policy enforcement."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self.hasher = PasswordHasher(
            time_cost=self.settings.password_argon2_time_cost,
            memory_cost=self.settings.password_argon2_memory_kib,
            parallelism=self.settings.password_argon2_parallelism,
        )

    def validate_policy(self, password: str) -> None:
        if len(password) < self.settings.password_min_length:
            raise ValueError(
                f"Password must contain at least {self.settings.password_min_length} characters."
            )
        if self.settings.password_require_mixed_classes:
            checks = (
                any(character.islower() for character in password),
                any(character.isupper() for character in password),
                any(character.isdigit() for character in password),
                any(not character.isalnum() for character in password),
            )
            if not all(checks):
                raise ValueError(
                    "Password must include upper-case, lower-case, numeric, and special characters."
                )

    def hash(self, password: str) -> str:
        self.validate_policy(password)
        return self.hasher.hash(password)

    def verify(self, password: str, password_hash: str) -> bool:
        try:
            return self.hasher.verify(password_hash, password)
        except (VerifyMismatchError, VerificationError, InvalidHashError):
            return False

    def needs_rehash(self, password_hash: str) -> bool:
        try:
            return self.hasher.check_needs_rehash(password_hash)
        except InvalidHashError:
            return True


class TokenService:
    """Issues and validates fixed-algorithm access tokens and opaque refresh tokens."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()

    def _encode_key(self) -> str:
        if self.settings.jwt_algorithm.startswith("HS"):
            if self.settings.jwt_secret_key is None:
                raise RuntimeError("JWT_SECRET_KEY is required for symmetric token signing.")
            return self.settings.jwt_secret_key.get_secret_value()
        if not self.settings.jwt_private_key:
            raise RuntimeError("JWT_PRIVATE_KEY is required for asymmetric token signing.")
        return self.settings.jwt_private_key.replace("\\n", "\n")

    def _decode_key(self) -> str:
        if self.settings.jwt_algorithm.startswith("HS"):
            if self.settings.jwt_secret_key is None:
                raise RuntimeError("JWT_SECRET_KEY is required for symmetric token validation.")
            return self.settings.jwt_secret_key.get_secret_value()
        if not self.settings.jwt_public_key:
            raise RuntimeError("JWT_PUBLIC_KEY is required for asymmetric token validation.")
        return self.settings.jwt_public_key.replace("\\n", "\n")

    def create_access_token(
        self,
        *,
        user_id: UUID,
        tenant_id: UUID,
        membership_id: UUID,
        role_assignment_id: UUID,
        role_code: str,
        session_id: UUID,
        now: datetime | None = None,
    ) -> tuple[str, datetime]:
        issued_at = now or datetime.now(timezone.utc)
        expires_at = issued_at + timedelta(minutes=self.settings.access_token_minutes)
        token_id = uuid4()
        payload: dict[str, Any] = {
            "sub": str(user_id),
            "tenant_id": str(tenant_id),
            "membership_id": str(membership_id),
            "role_assignment_id": str(role_assignment_id),
            "role_code": role_code,
            "session_id": str(session_id),
            "jti": str(token_id),
            "iat": issued_at,
            "nbf": issued_at,
            "exp": expires_at,
            "iss": self.settings.jwt_issuer,
            "aud": self.settings.jwt_audience,
            "typ": "access",
        }
        token = jwt.encode(
            payload,
            self._encode_key(),
            algorithm=self.settings.jwt_algorithm,
        )
        return token, expires_at

    def decode_access_token(self, token: str) -> AccessTokenClaims:
        try:
            payload = jwt.decode(
                token,
                self._decode_key(),
                algorithms=[self.settings.jwt_algorithm],
                audience=self.settings.jwt_audience,
                issuer=self.settings.jwt_issuer,
                leeway=self.settings.jwt_clock_skew_seconds,
                options={
                    "require": [
                        "sub",
                        "tenant_id",
                        "membership_id",
                        "role_assignment_id",
                        "role_code",
                        "session_id",
                        "jti",
                        "iat",
                        "nbf",
                        "exp",
                        "iss",
                        "aud",
                        "typ",
                    ]
                },
            )
            if payload.get("typ") != "access":
                raise InvalidTokenError("Unexpected token type")
            return AccessTokenClaims(
                subject=UUID(payload["sub"]),
                tenant_id=UUID(payload["tenant_id"]),
                membership_id=UUID(payload["membership_id"]),
                role_assignment_id=UUID(payload["role_assignment_id"]),
                role_code=str(payload["role_code"]),
                session_id=UUID(payload["session_id"]),
                token_id=UUID(payload["jti"]),
                expires_at=datetime.fromtimestamp(float(payload["exp"]), tz=timezone.utc),
            )
        except (InvalidTokenError, KeyError, TypeError, ValueError) as exc:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="The access token is invalid or expired.",
                headers={"WWW-Authenticate": "Bearer"},
            ) from exc

    @staticmethod
    def build_refresh_token(*, tenant_id: UUID, session_id: UUID) -> str:
        secret = secrets.token_urlsafe(48)
        return f"{tenant_id}.{session_id}.{secret}"

    @staticmethod
    def parse_refresh_token(token: str) -> tuple[UUID, UUID]:
        try:
            tenant_value, session_value, _ = token.split(".", maxsplit=2)
            return UUID(tenant_value), UUID(session_value)
        except (ValueError, AttributeError) as exc:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="The refresh token is malformed.",
            ) from exc

    @staticmethod
    def hash_opaque_token(token: str) -> str:
        return hashlib.sha256(token.encode("utf-8")).hexdigest()


def build_invitation_token(tenant_id: UUID) -> str:
    return f"{tenant_id}.{secrets.token_urlsafe(48)}"


def parse_invitation_tenant(token: str) -> UUID:
    try:
        tenant_value, _ = token.split(".", maxsplit=1)
        return UUID(tenant_value)
    except (ValueError, AttributeError) as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The invitation token is malformed.",
        ) from exc
