"""
main.py — PRPulse Query API entrypoint

Lifespan: init/close DB pool.
Exception handlers: HTTPException and bare Exception (no numeric codes).
Routers: health, repos, metrics, analytics.
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse

from app.db.database import init_db, close_db
from app.api import health, repos, metrics, analytics

logging.basicConfig(
    level  = logging.INFO,
    format = "%(asctime)s  %(levelname)-7s  %(name)s — %(message)s",
)
logger = logging.getLogger(__name__)


# ── Lifespan ──────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    logger.info("PRPulse Query API started")
    yield
    await close_db()
    logger.info("PRPulse Query API stopped")


# ── Application ───────────────────────────────────────────────────────────────

app = FastAPI(
    title       = "PRPulse Query API",
    description = "REST API for pull request analytics",
    version     = "1.0.0",
    lifespan    = lifespan,
)


# ── Exception handlers ────────────────────────────────────────────────────────
# Registered against exception classes, not numeric status codes.
# This is the correct FastAPI pattern — numeric handlers are unreliable
# because they fire on the HTTP status code of the *response*, not the
# exception type, and may miss exceptions raised before a response is sent.

@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    """
    Handle all FastAPI/Starlette HTTPExceptions.

    detail may be a dict (when services pass {"error": "..."})
    or a plain string (FastAPI validation errors).
    """
    detail = exc.detail
    if isinstance(detail, dict) and "error" in detail:
        content = detail
    else:
        content = {"error": str(detail)}

    # Never leak stack traces — log at WARNING for 4xx, ERROR for 5xx
    if exc.status_code >= 500:
        logger.error("HTTP %d: %s %s", exc.status_code, request.method, request.url)
    else:
        logger.warning("HTTP %d: %s", exc.status_code, content.get("error", ""))

    return JSONResponse(status_code=exc.status_code, content=content)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """
    Catch-all for unexpected exceptions.

    Logs the full exception (with traceback at DEBUG level) but returns
    a generic message so stack traces are never exposed to clients.
    """
    logger.error(
        "Unhandled exception on %s %s: %s: %s",
        request.method, request.url,
        type(exc).__name__, exc,
        exc_info=True,
    )
    return JSONResponse(
        status_code = 500,
        content     = {"error": "Internal server error"},
    )


# ── Routers ───────────────────────────────────────────────────────────────────

app.include_router(health.router,    tags=["Health"])
app.include_router(repos.router,     tags=["Repositories"])
app.include_router(metrics.router,   tags=["Metrics"])
app.include_router(analytics.router, tags=["Analytics"])