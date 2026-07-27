from __future__ import annotations

import json
from typing import Any

from redis.asyncio import Redis

from ..core.settings import Settings, get_settings


class RedisGateway:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self.client = Redis.from_url(
            self.settings.redis_url.get_secret_value(),
            decode_responses=True,
        )

    async def close(self) -> None:
        await self.client.aclose()

    async def ping(self) -> bool:
        return bool(await self.client.ping())

    async def set_json(self, key: str, value: Any, *, ttl_seconds: int) -> None:
        await self.client.set(key, json.dumps(value), ex=ttl_seconds)

    async def get_json(self, key: str) -> Any | None:
        value = await self.client.get(key)
        return json.loads(value) if value is not None else None

    async def acquire_lock(self, key: str, *, owner: str, ttl_seconds: int = 30) -> bool:
        return bool(await self.client.set(key, owner, nx=True, ex=ttl_seconds))

    async def release_lock(self, key: str, *, owner: str) -> bool:
        script = """
        if redis.call('get', KEYS[1]) == ARGV[1] then
          return redis.call('del', KEYS[1])
        end
        return 0
        """
        return bool(await self.client.eval(script, 1, key, owner))
