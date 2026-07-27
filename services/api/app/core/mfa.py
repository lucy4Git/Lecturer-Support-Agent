from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
import struct
import time
from urllib.parse import quote

from cryptography.fernet import Fernet, InvalidToken

from .settings import Settings, get_settings


class MFASecretProtector:
    """Encrypt TOTP secrets with a deployment key that never enters the database."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        configured = self.settings.mfa_secret_encryption_key
        if configured is not None:
            raw = configured.get_secret_value().encode("utf-8")
        elif self.settings.jwt_secret_key is not None:
            raw = self.settings.jwt_secret_key.get_secret_value().encode("utf-8")
        else:
            raise RuntimeError("MFA_SECRET_ENCRYPTION_KEY is required when no symmetric JWT key exists.")
        self._fernet = Fernet(base64.urlsafe_b64encode(hashlib.sha256(raw).digest()))

    def encrypt(self, secret: str) -> str:
        return self._fernet.encrypt(secret.encode("utf-8")).decode("ascii")

    def decrypt(self, ciphertext: str) -> str:
        try:
            return self._fernet.decrypt(ciphertext.encode("ascii")).decode("utf-8")
        except InvalidToken as exc:
            raise ValueError("The MFA secret cannot be decrypted with the configured key.") from exc


class TOTP:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()

    @staticmethod
    def generate_secret(bytes_length: int = 20) -> str:
        return base64.b32encode(secrets.token_bytes(bytes_length)).decode("ascii").rstrip("=")

    def code(self, secret: str, *, at_time: int | None = None) -> str:
        moment = int(time.time() if at_time is None else at_time)
        counter = moment // self.settings.mfa_totp_period_seconds
        padded = secret + "=" * ((8 - len(secret) % 8) % 8)
        key = base64.b32decode(padded.upper())
        digest = hmac.new(key, struct.pack(">Q", counter), hashlib.sha1).digest()
        offset = digest[-1] & 0x0F
        value = (struct.unpack(">I", digest[offset : offset + 4])[0] & 0x7FFFFFFF)
        modulus = 10 ** self.settings.mfa_totp_digits
        return str(value % modulus).zfill(self.settings.mfa_totp_digits)

    def verify(self, secret: str, code: str, *, at_time: int | None = None, window: int = 1) -> bool:
        if not code.isdigit() or len(code) != self.settings.mfa_totp_digits:
            return False
        moment = int(time.time() if at_time is None else at_time)
        period = self.settings.mfa_totp_period_seconds
        return any(
            hmac.compare_digest(self.code(secret, at_time=moment + offset * period), code)
            for offset in range(-window, window + 1)
        )

    def provisioning_uri(self, *, secret: str, account_name: str, issuer: str | None = None) -> str:
        issuer_value = issuer or self.settings.mfa_totp_issuer
        label = quote(f"{issuer_value}:{account_name}")
        return (
            f"otpauth://totp/{label}?secret={quote(secret)}&issuer={quote(issuer_value)}"
            f"&period={self.settings.mfa_totp_period_seconds}&digits={self.settings.mfa_totp_digits}"
            "&algorithm=SHA1"
        )


def generate_recovery_codes(count: int, *, groups: int = 2, group_length: int = 5) -> list[str]:
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    return [
        "-".join(
            "".join(secrets.choice(alphabet) for _ in range(group_length))
            for _ in range(groups)
        )
        for _ in range(count)
    ]
