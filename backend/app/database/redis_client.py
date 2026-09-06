"""Redis connection management."""
from __future__ import annotations

from redis.asyncio import Redis

from app.core.config import get_settings

_redis: Redis | None = None


def get_redis() -> Redis:
    global _redis
    if _redis is None:
        settings = get_settings()
        _redis = Redis.from_url(settings.redis_url, decode_responses=True)
    return _redis


async def check_redis_connection() -> bool:
    try:
        return bool(await get_redis().ping())
    except Exception:
        return False


async def dispose_redis() -> None:
    global _redis
    if _redis is not None:
        await _redis.aclose()
        _redis = None
