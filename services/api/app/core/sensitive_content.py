from __future__ import annotations

import base64
import hashlib

from cryptography.fernet import Fernet, InvalidToken

from .settings import Settings, get_settings


class SensitiveContentProtector:
    """Encrypt short-lived sensitive application payloads before database storage."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        configured = self.settings.message_content_encryption_key
        if configured is not None:
            raw = configured.get_secret_value().encode("utf-8")
        elif self.settings.mfa_secret_encryption_key is not None:
            raw = self.settings.mfa_secret_encryption_key.get_secret_value().encode("utf-8")
        elif self.settings.jwt_secret_key is not None:
            raw = self.settings.jwt_secret_key.get_secret_value().encode("utf-8")
        else:
            raise RuntimeError("MESSAGE_CONTENT_ENCRYPTION_KEY is required when no symmetric key exists.")
        self._fernet = Fernet(base64.urlsafe_b64encode(hashlib.sha256(raw).digest()))

    def encrypt(self, value: str) -> str:
        return self._fernet.encrypt(value.encode("utf-8")).decode("ascii")

    def decrypt(self, value: str) -> str:
        try:
            return self._fernet.decrypt(value.encode("ascii")).decode("utf-8")
        except InvalidToken as exc:
            raise ValueError("Sensitive message content cannot be decrypted with the configured key.") from exc
