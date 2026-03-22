"""
routers/webhook.py — Step 1: Multi-event routing

What changed from Phase 1:
  - Reads X-GitHub-Event header to get the real event type
  - Reads action field and merged flag to classify the event correctly
  - Includes repo_owner and repo_name from the payload (not from env vars)
  - Includes the full raw payload so the worker can extract whatever it needs
  - Returns the correct event_type in the response for debugging

Why include raw payload:
  Different event types need different fields from the payload.
  The webhook service should be fast and dumb — it just classifies and publishes.
  The worker extracts exactly what it needs from the raw JSON.
  This avoids a tight coupling between webhook and worker about what fields matter.

Event classification logic:
  X-GitHub-Event: pull_request
    action=opened                        → pr.opened
    action=synchronize                   → pr.updated  (new commits pushed)
    action=closed + merged=true          → pr.merged
    action=closed + merged=false         → pr.closed
    anything else                        → ignored

  X-GitHub-Event: pull_request_review
    action=submitted                     → pr.review
    anything else                        → ignored

  Anything else                          → ignored (ping, push, star, etc.)
"""

import json
import logging

import redis.asyncio as aioredis
from fastapi import APIRouter, Depends, Request

from app.config import STREAM_NAME
from app.dependencies import get_redis
from app.security.signature import verify_signature

logger = logging.getLogger(__name__)

router = APIRouter()


def _classify_event(github_event: str, payload: dict) -> str | None:
    """
    Determine the internal event_type string from the GitHub event header
    and payload. Returns None if the event should be silently ignored.

    GitHub sends X-GitHub-Event as a header.
    For pull_request events, the action field further specifies what happened.
    For closed events, merged=true means it was merged, false means abandoned.
    """

    action = payload.get("action", "")

    if github_event == "pull_request":
        if action == "opened":
            return "pr.opened"
        elif action == "synchronize":
            # New commits were pushed to the PR branch
            return "pr.updated"
        elif action == "closed":
            merged = payload.get("pull_request", {}).get("merged", False)
            return "pr.merged" if merged else "pr.closed"
        else:
            # reopened, assigned, labeled, etc. — not relevant
            return None

    elif github_event == "pull_request_review":
        if action == "submitted":
            return "pr.review"
        else:
            return None

    elif github_event == "ping":
        # GitHub sends a ping when a webhook is first registered
        # Always return 200 so GitHub marks the webhook as active
        return None

    else:
        # push, create, delete, issues, stars, etc. — all ignored
        return None


@router.post("/webhook", dependencies=[Depends(verify_signature)])
async def webhook_handler(
    request: Request,
    redis: aioredis.Redis = Depends(get_redis),
):
    """
    Receives any GitHub webhook event, classifies it, and publishes
    it to the Redis Stream with enough context for the worker.

    Returns HTTP 200 for all events — including ignored ones.
    GitHub will retry on non-200, so we always return 200.
    """

    # Read the GitHub event type from the header
    # This header is what tells us pull_request vs pull_request_review vs push
    github_event: str = request.headers.get("X-GitHub-Event", "")

    # Read the raw bytes first (needed by signature verification which already
    # ran, but we need to parse JSON ourselves here)
    raw_body = await request.body()

    try:
        payload = json.loads(raw_body)
    except json.JSONDecodeError:
        logger.warning("Webhook received non-JSON body — ignoring")
        return {"status": "ignored", "reason": "invalid JSON"}

    # Classify the event
    event_type = _classify_event(github_event, payload)

    if event_type is None:
        action = payload.get("action", "unknown")
        logger.debug(
            "Ignoring GitHub event: X-GitHub-Event=%s action=%s",
            github_event, action,
        )
        return {"status": "ignored", "reason": f"event {github_event}/{action} not tracked"}

    # Extract PR number — present on all event types we care about
    pr_data = payload.get("pull_request") or payload.get("review", {})
    pr_number = (
        payload.get("pull_request", {}).get("number")
        or payload.get("number")
    )

    if not pr_number:
        logger.warning(
            "Event %s has no pr_number — ignoring (payload keys: %s)",
            event_type, list(payload.keys()),
        )
        return {"status": "ignored", "reason": "no pr_number found"}

    # Extract repo identity from the payload — not from env vars.
    # This is what makes multi-repo work: every event carries its own repo.
    repo = payload.get("repository", {})
    repo_owner = repo.get("owner", {}).get("login", "")
    repo_name  = repo.get("name", "")

    if not repo_owner or not repo_name:
        logger.warning(
            "Event %s missing repository info — ignoring",
            event_type,
        )
        return {"status": "ignored", "reason": "missing repository info"}

    # Publish to Redis Stream
    # raw_payload is the full JSON so the worker can extract what it needs
    # without us having to anticipate every field upfront
    stream_id = await redis.xadd(
        STREAM_NAME,
        {
            "event_type":  event_type,
            "pr_number":   str(pr_number),
            "repo_owner":  repo_owner,
            "repo_name":   repo_name,
            "raw_payload": raw_body.decode("utf-8"),
        },
        maxlen      = 10_000,   # keep last 10k events in the stream
        approximate = True,
    )

    logger.info(
        "Published %s | PR #%s | %s/%s | stream_id=%s",
        event_type, pr_number, repo_owner, repo_name, stream_id,
    )

    return {
        "status":     "accepted",
        "event_type": event_type,
        "pr_number":  pr_number,
        "repo":       f"{repo_owner}/{repo_name}",
        "stream_id":  stream_id,
    }
