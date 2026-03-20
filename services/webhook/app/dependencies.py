import redis.asyncio as aioredis

from app.config import REDIS_URL

# ── Redis client ──────────────────────────────────────────────────────────────
# Created once when the module is first imported.
# Reused across all requests — no new connection per request.
_redis_client: aioredis.Redis = aioredis.from_url(
    REDIS_URL,
    decode_responses=True,
)


def get_redis() -> aioredis.Redis:
    """
    Returns the shared Redis client.
    Used as a FastAPI dependency in route handlers.

    Example usage in a route:
        async def my_route(redis = Depends(get_redis)):
            await redis.ping()
    """
    return _redis_client