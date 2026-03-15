"""
db/client.py — asyncpg connection pool lifecycle

Responsibilities:
  - Create a single asyncpg pool once at worker startup
  - Run schema initialisation (schema.sql) on first connect
  - Expose get_pool() for use by the repository layer
  - Close the pool cleanly on graceful shutdown

Design rule:
  Never create a raw connection per-event.
  All callers receive a pooled connection via get_pool().acquire().
"""

import logging
import os
from pathlib import Path

import asyncpg

from app.config import DATABASE_URL

logger = logging.getLogger(__name__)

# Module-level pool — created once, shared for worker lifetime
_pool: asyncpg.Pool | None = None

# Resolve schema.sql relative to this file's parent (services/worker/db/)
_SCHEMA_PATH = Path(__file__).resolve().parents[2] / "db" / "schema.sql"


async def init_db() -> None:
    """
    Create the asyncpg connection pool and run schema initialisation.

    Called once at worker startup before the Redis loop begins.
    Raises on connection failure so the worker fails fast with a
    clear error rather than silently processing events without a DB.
    """
    global _pool

    logger.info("Connecting to PostgreSQL …")
    _pool = await asyncpg.create_pool(
        DATABASE_URL,
        min_size = 2,    # keep 2 connections warm
        max_size = 10,   # scale up to 10 under load
    )

    # Run schema DDL so tables and indexes exist before any insert
    schema_sql = _SCHEMA_PATH.read_text()
    async with _pool.acquire() as conn:
        await conn.execute(schema_sql)

    logger.info("PostgreSQL pool ready (min=2, max=10)")


def get_pool() -> asyncpg.Pool:
    """
    Return the active connection pool.
    Raises RuntimeError if init_db() was never called.
    """
    if _pool is None:
        raise RuntimeError(
            "Database pool not initialised. "
            "Call await db.client.init_db() at worker startup."
        )
    return _pool


async def close_db() -> None:
    """Release all pooled connections. Call on graceful shutdown."""
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None
        logger.info("PostgreSQL pool closed")