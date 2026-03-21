# shared/redis/client.py
#
# A single place to create the Redis connection.
# Both the webhook service and the worker import from here.
#
# Why a shared client factory:
#   Without this, each service would write its own redis.from_url(...)
#   with its own URL format. If anything changes (password, port, etc.)
#   you'd have to update it in multiple places. Here it's one place.

import redis.asyncio as aioredis


def create_redis_client(redis_url: str) -> aioredis.Redis:
    """
    Creates and returns an async Redis client.

    Args:
        redis_url: full Redis URL, e.g. "redis://localhost:6379/0"
                   or "redis://:password@redis:6379/0" inside Docker

    Returns:
        An aioredis.Redis instance ready to use.
        The connection is lazy — it only actually connects on first command.

    Usage:
        from shared.redis.client import create_redis_client
        redis = create_redis_client("redis://localhost:6379/0")
        await redis.ping()
    """
    return aioredis.from_url(
        redis_url,
        decode_responses=True,  # return strings, not raw bytes
    )
