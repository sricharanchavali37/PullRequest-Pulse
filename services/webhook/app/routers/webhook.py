import logging

import redis.asyncio as aioredis
from fastapi import APIRouter, Depends, Request

from app.config import STREAM_NAME
from app.dependencies import get_redis
from app.security.signature import verify_signature

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/webhook", dependencies=[Depends(verify_signature)])
async def webhook_handler(
    request: Request,
    redis: aioredis.Redis = Depends(get_redis),
):
    """
    Receives a GitHub webhook event, extracts the PR number,
    and publishes it to the Redis Stream.

    Returns HTTP 200 immediately — all analysis happens in the worker.

    The `dependencies=[Depends(verify_signature)]` line runs signature
    verification BEFORE this function body executes. If the signature
    is wrong, FastAPI returns 401 and this code never runs.
    """

    payload = await request.json()
    pr_number = payload.get("number")

    if not pr_number:
        # Not a PR event we care about (e.g. a ping event from GitHub)
        # Return 200 so GitHub doesn't retry — we just don't publish it
        return {"status": "ignored", "reason": "no pr_number in payload"}

    stream_id = await redis.xadd(
        STREAM_NAME,
        {
            "event_type": "pr.opened",
            "pr_number":  str(pr_number),
        },
    )

    logger.info("Published PR #%s to %s | stream_id=%s", pr_number, STREAM_NAME, stream_id)

    return {"status": "accepted", "pr_number": pr_number, "stream_id": stream_id}