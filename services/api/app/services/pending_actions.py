"""Server-side pending action store for deterministic write confirmation.

Stores opaque tokens server-side so the frontend cannot tamper with entity IDs.
A malicious client can only call Confirm or Cancel -- it cannot change what is confirmed.
"""
from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from typing import Any
from uuid import UUID, uuid4

_TTL_SECONDS = 300  # 5 minutes to confirm or cancel

@dataclass
class PendingAction:
    token: str
    user_id: UUID
    tenant_id: UUID
    action_type: str          # e.g. "assign_lecturer", "create_org_unit"
    payload: dict[str, Any]   # resolved entity IDs -- never client-supplied
    label: str                # human-readable confirmation card title
    details: list[dict]       # [{key, value}] rows for the confirmation card
    expires_at: float         # time.monotonic()


class PendingActionStore:
    """In-process store with monotonic-clock TTL expiry.

    Safe for single-process deployments (dev/staging).
    For multi-process production, replace with Redis or a DB table.
    """

    _instance: PendingActionStore | None = None

    def __init__(self) -> None:
        self._store: dict[str, PendingAction] = {}
        self._lock = asyncio.Lock()

    @classmethod
    def get(cls) -> PendingActionStore:
        if cls._instance is None:
            cls._instance = PendingActionStore()
        return cls._instance

    async def create(
        self,
        *,
        user_id: UUID,
        tenant_id: UUID,
        action_type: str,
        payload: dict[str, Any],
        label: str,
        details: list[dict],
    ) -> str:
        token = str(uuid4())
        async with self._lock:
            self._expire_stale()
            self._store[token] = PendingAction(
                token=token,
                user_id=user_id,
                tenant_id=tenant_id,
                action_type=action_type,
                payload=payload,
                label=label,
                details=details,
                expires_at=time.monotonic() + _TTL_SECONDS,
            )
        return token

    async def claim(
        self,
        *,
        token: str,
        user_id: UUID,
        tenant_id: UUID,
    ) -> PendingAction | None:
        """Claim and remove an action. Returns None if token is invalid/expired/wrong owner."""
        async with self._lock:
            self._expire_stale()
            action = self._store.get(token)
            if action is None:
                return None
            if action.user_id != user_id or action.tenant_id != tenant_id:
                return None
            del self._store[token]
        return action

    async def cancel(self, *, token: str, user_id: UUID, tenant_id: UUID) -> bool:
        """Cancel (discard) a pending action without executing it."""
        async with self._lock:
            action = self._store.get(token)
            if action and action.user_id == user_id and action.tenant_id == tenant_id:
                del self._store[token]
                return True
        return False

    def _expire_stale(self) -> None:
        now = time.monotonic()
        stale = [k for k, v in self._store.items() if v.expires_at < now]
        for k in stale:
            del self._store[k]
