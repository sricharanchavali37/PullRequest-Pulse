"""
worker.py — Phase-4 Production Worker

Preserves all Phase-2/3 logic (Redis loop, GitHub fetch, diff parse,
risk score) and adds:

  • PostgreSQL persistence via repository layer
  • Per-event retry with exponential backoff (1s / 2s / 4s)
  • Dead Letter Queue (prpulse:events:failed) after retries exhausted
  • XAUTOCLAIM recovery task every 30 seconds with cursor tracking
  • Correct ACK ordering (persist → ACK)
  • Structured logging throughout
  • Graceful shutdown — closes Redis, DB pool, HTTP client

ACK ordering rule (enforced):
  analyse → persist → ACK
  ACK never fires before a successful DB write.
"""

import asyncio
import logging
import socket
import time

import redis.asyncio as aioredis
from redis.exceptions import ResponseError

from app.config import (
    REDIS_URL,
    STREAM_NAME,
    FAILED_STREAM_NAME,
    GROUP_NAME,
    GITHUB_OWNER,
    GITHUB_REPO,
    RETRY_BACKOFF,
    MAX_RETRIES,
    RECOVERY_INTERVAL_SECONDS,
    RECOVERY_IDLE_MS,
    RECOVERY_BATCH_SIZE,
    validate_config,
)
from app.github.client  import fetch_pr_metadata, fetch_pr_files, close_client
from app.diff.parser    import parse_diff
from app.risk.scorer    import compute_risk
from app.models.pr_data import PRAnalysis
from app.db.client      import init_db, close_db
from app.db.repository  import insert_pull_request, insert_analysis_result

logging.basicConfig(
    level  = logging.INFO,
    format = "%(asctime)s  %(levelname)-7s  %(name)s — %(message)s",
)
logger = logging.getLogger(__name__)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _consumer_name() -> str:
    return f"worker-{socket.gethostname()}"


async def _ensure_consumer_group(redis_client: aioredis.Redis) -> None:
    """Create consumer group idempotently. BUSYGROUP = already exists."""
    try:
        await redis_client.xgroup_create(
            name      = STREAM_NAME,
            groupname = GROUP_NAME,
            id        = "$",
            mkstream  = True,
        )
        logger.info("Consumer group '%s' created on stream '%s'", GROUP_NAME, STREAM_NAME)
    except ResponseError as exc:
        if "BUSYGROUP" in str(exc):
            logger.info("Consumer group '%s' already exists — continuing", GROUP_NAME)
        else:
            raise


# ── Analysis pipeline ─────────────────────────────────────────────────────────

async def _analyse_pr(pr_number: int) -> PRAnalysis:
    """
    Run fetch → parse → score for one PR.
    Raises on any failure — caller drives retry logic.
    """
    metadata = await fetch_pr_metadata(GITHUB_OWNER, GITHUB_REPO, pr_number)
    author   = metadata.get("user", {}).get("login", "unknown")

    files       = await fetch_pr_files(GITHUB_OWNER, GITHUB_REPO, pr_number)
    diff_result = parse_diff(files)
    risk_result = compute_risk(
        files_changed    = diff_result["files_changed"],
        lines_added      = diff_result["lines_added"],
        lines_removed    = diff_result["lines_removed"],
        breaking_changes = diff_result["breaking_changes"],
    )

    return PRAnalysis(
        pr_number        = pr_number,
        author           = author,
        files_changed    = diff_result["files_changed"],
        lines_added      = diff_result["lines_added"],
        lines_removed    = diff_result["lines_removed"],
        breaking_changes = diff_result["breaking_changes"],
        risk_score       = risk_result["risk_score"],
        risk_level       = risk_result["risk_level"],
    )


async def _persist(analysis: PRAnalysis) -> None:
    """
    Write PR and analysis rows to PostgreSQL.

    insert_pull_request is idempotent (ON CONFLICT DO NOTHING).
    insert_analysis_result depends on the FK — pull_requests row must
    exist first, which insert_pull_request guarantees.

    Raises on DB failure — caller drives retry logic.
    """
    await insert_pull_request(
        pr_number  = analysis.pr_number,
        author     = analysis.author,
        repo_owner = GITHUB_OWNER,
        repo_name  = GITHUB_REPO,
    )
    await insert_analysis_result(
        pr_number     = analysis.pr_number,
        files_changed = analysis.files_changed,
        lines_added   = analysis.lines_added,
        lines_removed = analysis.lines_removed,
        risk_score    = analysis.risk_score,
        risk_level    = analysis.risk_level,
    )


def _log_analysis(analysis: PRAnalysis) -> None:
    """Emit the completed analysis result as structured log lines."""
    logger.info("Processing PR #%d", analysis.pr_number)
    logger.info("  Author:        %s", analysis.author)
    logger.info("  Files changed: %d", analysis.files_changed)
    logger.info("  Lines added:   %d", analysis.lines_added)
    logger.info("  Lines removed: %d", analysis.lines_removed)
    if analysis.breaking_changes:
        logger.info("  Breaking changes:")
        for bc in analysis.breaking_changes:
            logger.info("    * %s in %s", bc.signal_type, bc.filename)
    logger.info("  Risk Score: %g", analysis.risk_score)
    logger.info("  Risk Level: %s", analysis.risk_level)


# ── Dead Letter Queue ─────────────────────────────────────────────────────────

async def _send_to_dlq(
    redis_client: aioredis.Redis,
    event_type:   str,
    pr_number:    str,
    error:        str,
    retry_count:  int,
) -> None:
    """
    Publish a failed event to FAILED_STREAM_NAME (DLQ).
    Uses the named constant — never an inline string.
    """
    await redis_client.xadd(
        FAILED_STREAM_NAME,
        {
            "event_type":  event_type,
            "pr_number":   pr_number,
            "error":       error,
            "retry_count": str(retry_count),
            "timestamp":   str(int(time.time())),
        },
    )
    logger.warning(
        "PR #%s sent to DLQ after %d retries: %s",
        pr_number, retry_count, error,
    )


# ── Per-message handler with retry ───────────────────────────────────────────

async def _handle_message(
    redis_message_id: str,
    fields:           dict,
    redis_client:     aioredis.Redis,
) -> None:
    """
    Process one Redis Stream message end-to-end.

    Retry schedule: attempt 1 → sleep 1s → attempt 2 → sleep 2s → attempt 3.
    If all attempts fail: publish to DLQ, then ACK (clears PEL).
    ACK fires ONLY after successful DB persistence.
    """
    event_type = fields.get("event_type", "unknown")
    pr_number  = fields.get("pr_number",  "")

    # Skip non-PR events immediately — nothing to persist, ACK and move on
    if event_type != "pr.opened":
        logger.info("Skipping event '%s' (PR #%s)", event_type, pr_number)
        await redis_client.xack(STREAM_NAME, GROUP_NAME, redis_message_id)
        return

    if not pr_number:
        logger.error("Message %s has no pr_number — discarding", redis_message_id)
        await redis_client.xack(STREAM_NAME, GROUP_NAME, redis_message_id)
        return

    # Guard against malformed values (e.g. "abc", "1.5") that would cause
    # int() to raise a ValueError deep inside the retry loop, burning all
    # three retries on an unrecoverable input error.  Catch it once here,
    # discard the message cleanly, and move on.
    try:
        pr_number_int = int(pr_number)
    except ValueError:
        logger.error(
            "Invalid pr_number '%s' in message %s — discarding",
            pr_number, redis_message_id,
        )
        await redis_client.xack(STREAM_NAME, GROUP_NAME, redis_message_id)
        return

    last_error: str = ""

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            logger.info("PR #%s — attempt %d/%d", pr_number, attempt, MAX_RETRIES)

            # ── Analyse ──────────────────────────────────────────────────────
            analysis = await _analyse_pr(pr_number_int)

            # ── Persist — MUST succeed before ACK ────────────────────────────
            await _persist(analysis)
            logger.info("PR #%s — persisted to database", pr_number)

            # ── Log output ───────────────────────────────────────────────────
            _log_analysis(analysis)

            # ── ACK only after successful persistence ─────────────────────────
            await redis_client.xack(STREAM_NAME, GROUP_NAME, redis_message_id)
            logger.info("PR #%s — event acknowledged", pr_number)
            return   # success — exit retry loop

        except Exception as exc:
            last_error = str(exc)
            logger.warning("PR #%s — attempt %d failed: %s", pr_number, attempt, exc)
            if attempt < MAX_RETRIES:
                backoff = RETRY_BACKOFF[attempt - 1]
                logger.info("PR #%s — retrying in %ds …", pr_number, backoff)
                await asyncio.sleep(backoff)

    # All retries exhausted — publish to DLQ then ACK to clear PEL
    await _send_to_dlq(
        redis_client = redis_client,
        event_type   = event_type,
        pr_number    = pr_number,
        error        = last_error,
        retry_count  = MAX_RETRIES,
    )
    await redis_client.xack(STREAM_NAME, GROUP_NAME, redis_message_id)
    logger.error(
        "PR #%s — permanently failed after %d retries; sent to DLQ",
        pr_number, MAX_RETRIES,
    )


# ── PEL recovery task ─────────────────────────────────────────────────────────

async def _recovery_loop(redis_client: aioredis.Redis, consumer: str) -> None:
    """
    Background task: reclaims messages idle in the PEL.

    Runs every RECOVERY_INTERVAL_SECONDS seconds.

    Uses XAUTOCLAIM to find messages that have been idle longer than
    RECOVERY_IDLE_MS.  These are messages a worker read but crashed
    before ACKing.

    Cursor tracking:
      XAUTOCLAIM returns a next_cursor indicating where the scan
      stopped.  We track this cursor across iterations so each scan
      continues from where the previous one left off rather than
      restarting from "0-0" every time.  When a full pass completes
      (cursor returns to "0-0"), we reset and wait for the next interval.

    Reclaimed messages are reprocessed through _handle_message() so the
    full retry / DLQ / ACK logic applies.
    """
    logger.info(
        "PEL recovery task started "
        "(interval=%ds, idle_threshold=%dms, batch=%d)",
        RECOVERY_INTERVAL_SECONDS, RECOVERY_IDLE_MS, RECOVERY_BATCH_SIZE,
    )

    # Start cursor at the beginning of the PEL on first run
    cursor = "0-0"

    while True:
        await asyncio.sleep(RECOVERY_INTERVAL_SECONDS)
        try:
            # XAUTOCLAIM returns (next_cursor, [(id, fields), ...], [deleted_ids])
            result = await redis_client.xautoclaim(
                name          = STREAM_NAME,
                groupname     = GROUP_NAME,
                consumername  = consumer,
                min_idle_time = RECOVERY_IDLE_MS,
                start_id      = cursor,
                count         = RECOVERY_BATCH_SIZE,
            )

            next_cursor, claimed_entries, _deleted = result

            if not claimed_entries:
                # Nothing claimed this pass — reset cursor for next interval
                cursor = "0-0"
                continue

            logger.info(
                "PEL recovery: reclaimed %d idle message(s) "
                "(cursor %s → %s)",
                len(claimed_entries), cursor, next_cursor,
            )

            for msg_id, fields in claimed_entries:
                logger.info("Reprocessing recovered message %s", msg_id)
                await _handle_message(msg_id, fields, redis_client)

            # Advance cursor so the next call continues from where we stopped.
            # If XAUTOCLAIM signals it reached the end (returns "0-0"), the
            # next interval will start a fresh full-PEL scan.
            cursor = next_cursor if next_cursor != "0-0" else "0-0"

        except Exception as exc:
            # Never let a recovery error crash the background task
            logger.error("PEL recovery error: %s", exc)
            cursor = "0-0"   # safe reset on error


# ── Main entry point ──────────────────────────────────────────────────────────

async def run_worker() -> None:
    """
    Full startup sequence:
      1. Validate config (fail fast on missing env vars)
      2. Init DB pool + run schema DDL
      3. Connect to Redis
      4. Ensure consumer group exists
      5. Start PEL recovery background task
      6. Run infinite XREADGROUP loop
      7. On shutdown: cancel recovery task, close all resources
    """
    validate_config()

    consumer = _consumer_name()
    logger.info("Worker starting — consumer: %s", consumer)

    # ── Database ──────────────────────────────────────────────────────────────
    await init_db()

    # ── Redis ─────────────────────────────────────────────────────────────────
    redis_client = await aioredis.from_url(
        REDIS_URL,
        decode_responses=True,
    )
    await redis_client.ping()
    logger.info("Redis connection established")
    logger.info("Stream:        %s", STREAM_NAME)
    logger.info("Failed stream: %s", FAILED_STREAM_NAME)
    logger.info("Consumer group:%s", GROUP_NAME)

    await _ensure_consumer_group(redis_client)

    # ── PEL recovery background task ──────────────────────────────────────────
    recovery_task = asyncio.create_task(
        _recovery_loop(redis_client, consumer)
    )

    logger.info("Listening to Redis stream …")

    try:
        while True:
            results = await redis_client.xreadgroup(
                groupname    = GROUP_NAME,
                consumername = consumer,
                streams      = {STREAM_NAME: ">"},
                count        = 1,
                block        = 5000,
            )

            if not results:
                await asyncio.sleep(0.1)
                continue

            for _stream_name, messages in results:
                for redis_message_id, fields in messages:
                    await _handle_message(redis_message_id, fields, redis_client)

    finally:
        logger.info("Shutting down — closing resources …")
        recovery_task.cancel()
        try:
            await recovery_task
        except asyncio.CancelledError:
            pass
        await close_client()       # httpx AsyncClient
        await close_db()           # asyncpg pool
        await redis_client.aclose()
        logger.info("Worker shutdown complete")