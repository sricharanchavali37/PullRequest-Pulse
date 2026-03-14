"""
worker.py — Phase-3 PR Analysis Worker

Preserves all Phase-2 Redis consumer group logic unchanged.
Extends the per-message handler with a full async analysis pipeline.

Pipeline per pr.opened event:
  1. Fetch PR metadata from GitHub API
  2. Fetch changed files (paginated)
  3. Parse diffs for risk signals
  4. Compute deterministic risk score
  5. Print structured analysis result
  6. XACK the Redis message

Safety contract:
  - Analysis errors are caught per-message — the worker never terminates
    because a single PR failed.
  - XACK always runs in a finally block so messages never pile up
    in the Pending Entries List due to processing failures.
"""

import asyncio
import logging
import socket

import redis.asyncio as aioredis
from redis.exceptions import ResponseError

from app.config import (
    REDIS_URL, STREAM_NAME, GROUP_NAME,
    GITHUB_OWNER, GITHUB_REPO,
    validate_config,
)
from app.github.client  import fetch_pr_metadata, fetch_pr_files, close_client
from app.diff.parser    import parse_diff
from app.risk.scorer    import compute_risk
from app.models.pr_data import PRAnalysis

logging.basicConfig(
    level  = logging.INFO,
    format = "%(asctime)s  %(levelname)-7s  %(name)s — %(message)s",
)
logger = logging.getLogger(__name__)


# ── Consumer name ─────────────────────────────────────────────────────────────

def _consumer_name() -> str:
    return f"worker-{socket.gethostname()}"


# ── Consumer group bootstrap ──────────────────────────────────────────────────

async def _ensure_consumer_group(client: aioredis.Redis) -> None:
    """
    Create the consumer group idempotently.
    BUSYGROUP means it already exists — not an error.
    All other ResponseErrors propagate.
    """
    try:
        await client.xgroup_create(
            name      = STREAM_NAME,
            groupname = GROUP_NAME,
            id        = "$",
            mkstream  = True,
        )
        print(f"Consumer group '{GROUP_NAME}' created on stream '{STREAM_NAME}'")
    except ResponseError as exc:
        if "BUSYGROUP" in str(exc):
            print(f"Consumer group '{GROUP_NAME}' already exists — continuing")
        else:
            raise


# ── Output formatter ──────────────────────────────────────────────────────────

def _print_analysis(analysis: PRAnalysis) -> None:
    """Print a structured PR analysis result to stdout."""
    print(f"\nProcessing PR #{analysis.pr_number}\n")
    print(f"Author: {analysis.author}")
    print(f"Files changed: {analysis.files_changed}")
    print(f"Lines added: {analysis.lines_added}")
    print(f"Lines removed: {analysis.lines_removed}")

    if analysis.breaking_changes:
        print("\nBreaking changes detected:\n")
        for bc in analysis.breaking_changes:
            print(f"  * {bc.signal_type} in {bc.filename}")
    else:
        print("\nNo breaking changes detected.")

    print(f"\nRisk Score: {int(analysis.risk_score)}")
    print(f"Risk Level: {analysis.risk_level}")


# ── Analysis pipeline ─────────────────────────────────────────────────────────

async def _analyse_pr(pr_number: int) -> PRAnalysis:
    """
    Run the full analysis pipeline for one PR number.
    Raises on any error — caller handles it.
    """
    metadata    = await fetch_pr_metadata(GITHUB_OWNER, GITHUB_REPO, pr_number)
    author      = metadata.get("user", {}).get("login", "unknown")

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


# ── Per-message handler ───────────────────────────────────────────────────────

async def _handle_message(
    redis_message_id: str,
    fields:           dict,
    redis_client:     aioredis.Redis,
) -> None:
    """
    Process one Redis Stream message.
    XACK always runs — success or failure — via the finally block.
    """
    event_type = fields.get("event_type", "unknown")
    pr_number  = fields.get("pr_number",  "")

    try:
        if event_type != "pr.opened":
            print(f"\nSkipping event '{event_type}' (PR #{pr_number})")
            return

        if not pr_number:
            logger.error("Message %s missing pr_number — skipping", redis_message_id)
            return

        analysis = await _analyse_pr(int(pr_number))
        _print_analysis(analysis)

    except Exception as exc:
        logger.error(
            "Analysis failed for PR #%s (message %s): %s",
            pr_number, redis_message_id, exc,
        )

    finally:
        await redis_client.xack(STREAM_NAME, GROUP_NAME, redis_message_id)
        print("\nEvent acknowledged")


# ── Main worker loop ──────────────────────────────────────────────────────────

async def run_worker() -> None:
    """
    Validate config, connect to Redis, run the infinite XREADGROUP loop.
    """
    # Fail fast if required env vars are not set
    validate_config()

    consumer = _consumer_name()

    print("Worker starting")

    redis_client = await aioredis.from_url(
        REDIS_URL,
        decode_responses=True,
    )

    await redis_client.ping()
    print("Redis connection established")
    print(f"\nStream: {STREAM_NAME}")
    print(f"Consumer group: {GROUP_NAME}")
    print(f"Consumer name: {consumer}")

    await _ensure_consumer_group(redis_client)

    print("\nListening to Redis stream...")

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
        # Release the shared HTTP client connection pool on shutdown
        await close_client()
        await redis_client.aclose()