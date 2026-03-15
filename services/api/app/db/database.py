"""
db/database.py — asyncpg connection pool lifecycle

Responsibilities:
  - Create a single asyncpg pool at FastAPI startup
  - Provide a FastAPI dependency that yields a pooled connection
  - Close the pool cleanly at shutdown

Usage in routes:
    async def my_route(conn = Depends(get_db)):
        rows = await conn.fetch("SELECT ...")

Design:
  One pool for the process lifetime.  Never create a raw connection
  per-request — that defeats the purpose of pooling.
"""

import logging
from typing import AsyncGenerator

import asyncpg

from app.config import DATABASE_URL

logger = logging.getLogger(__name__)

# Module-level pool, initialised once at startup
_pool: asyncpg.Pool | None = None


async def init_db() -> None:
    """
    Create the asyncpg connection pool.
    Called once inside FastAPI's lifespan startup hook.
    """
    global _pool
    logger.info("Connecting to PostgreSQL …")
    _pool = await asyncpg.create_pool(
        DATABASE_URL,
        min_size = 2,
        max_size = 10,
    )
    logger.info("PostgreSQL pool ready (min=2, max=10)")


async def close_db() -> None:
    """
    Release all pooled connections.
    Called once inside FastAPI's lifespan shutdown hook.
    """
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None
        logger.info("PostgreSQL pool closed")


async def get_db() -> AsyncGenerator[asyncpg.Connection, None]:
    """
    FastAPI dependency: yields one connection from the pool.

    The connection is returned to the pool when the request finishes,
    whether it succeeds or raises an exception.

    Usage:
        @router.get("/example")
        async def example(conn: asyncpg.Connection = Depends(get_db)):
            ...
    """
    if _pool is None:
        raise RuntimeError(
            "Database pool not initialised. "
            "Ensure init_db() was called during application startup."
        )
    async with _pool.acquire() as conn:
        yield conn