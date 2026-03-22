"""
main.py — PRPulse Query API entrypoint (Step 3: Tier-3 endpoints added)

New in this version:
  - tier3 router registered with tag "Tier-3 Analytics"
  - Exposes: cycle-time, reviewers, trends
"""

import asyncio
import logging
from contextlib import asynccontextmanager

import redis.asyncio as aioredis
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import REDIS_HOST, REDIS_PORT
from app.db.database import init_db, close_db
from app.api import health, repos, metrics, analytics, events, tier3
from app.sse.broadcaster import broadcaster_loop

logging.basicConfig(
    level  = logging.INFO,
    format = "%(asctime)s  %(levelname)-7s  %(name)s — %(message)s",
)
logger = logging.getLogger(__name__)

_broadcaster_task: asyncio.Task | None = None


# ── Lifespan ──────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    global _broadcaster_task

    await init_db()

    redis_client = aioredis.from_url(
        f"redis://{REDIS_HOST}:{REDIS_PORT}/0",
        decode_responses=True,
    )
    _broadcaster_task = asyncio.create_task(broadcaster_loop(redis_client))
    logger.info("PRPulse Query API started")

    yield

    if _broadcaster_task:
        _broadcaster_task.cancel()
        try:
            await _broadcaster_task
        except asyncio.CancelledError:
            pass

    await redis_client.aclose()
    await close_db()
    logger.info("PRPulse Query API stopped")


# ── Application ───────────────────────────────────────────────────────────────

app = FastAPI(
    title       = "PRPulse Query API",
    description = "REST API for pull request analytics + live feed",
    version     = "3.0.0",
    lifespan    = lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins = ["*"],
    allow_methods = ["GET"],
    allow_headers = ["*"],
)


# ── Exception handlers ────────────────────────────────────────────────────────

@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    detail  = exc.detail
    content = detail if isinstance(detail, dict) and "error" in detail else {"error": str(detail)}
    if exc.status_code >= 500:
        logger.error("HTTP %d: %s %s", exc.status_code, request.method, request.url)
    else:
        logger.warning("HTTP %d: %s", exc.status_code, content.get("error", ""))
    return JSONResponse(status_code=exc.status_code, content=content)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.error(
        "Unhandled exception on %s %s: %s: %s",
        request.method, request.url, type(exc).__name__, exc,
        exc_info=True,
    )
    return JSONResponse(status_code=500, content={"error": "Internal server error"})


# ── Routers ───────────────────────────────────────────────────────────────────

app.include_router(health.router,    tags=["Health"])
app.include_router(repos.router,     tags=["Repositories"])
app.include_router(metrics.router,   tags=["Metrics"])
app.include_router(analytics.router, tags=["Analytics"])
app.include_router(events.router,    tags=["Live Feed"])
app.include_router(tier3.router,     tags=["Tier-3 Analytics"])   # Step 3
