"""
sse/broadcaster.py — Background task that reads from prpulse:notifications
and pushes events to all connected SSE clients.

How it works:
  1. On API startup, this coroutine is started as a background task.
  2. It runs an infinite loop reading from prpulse:notifications using XREAD.
  3. For each notification it receives, it calls manager.broadcast() which
     puts the JSON string into every connected client's asyncio.Queue.
  4. Each SSE endpoint reads from its own queue and sends the event to the browser.

Why XREAD instead of XREADGROUP:
  The broadcaster is a single process reading all notifications.
  There's no need for consumer group load-balancing here — we WANT
  every notification to go to every connected client (broadcast).
  XREAD with a cursor tracks where we left off if the broadcaster restarts.
"""

import asyncio
import json
import logging

import redis.asyncio as aioredis

from app.sse.connection_manager import manager

logger = logging.getLogger(__name__)

NOTIFICATIONS_STREAM = "prpulse:notifications"


async def broadcaster_loop(redis_client: aioredis.Redis) -> None:
    """
    Reads from prpulse:notifications and broadcasts to all SSE clients.
    Runs as a background asyncio task for the lifetime of the API process.
    Never raises — catches all exceptions and continues.
    """
    logger.info("SSE broadcaster started — reading from %s", NOTIFICATIONS_STREAM)

    # Start reading from the latest entry only (don't replay old notifications)
    last_id = "$"

    while True:
        try:
            # XREAD blocks for up to 1 second waiting for new entries.
            # Returns None if nothing arrives within the timeout.
            results = await redis_client.xread(
                streams = {NOTIFICATIONS_STREAM: last_id},
                block   = 1000,   # milliseconds
                count   = 10,     # read up to 10 at once if they pile up
            )

            if not results:
                continue

            for _stream_name, messages in results:
                for message_id, fields in messages:
                    last_id = message_id   # advance cursor

                    # Build the JSON payload the dashboard will receive
                    payload = {
                        "pr_number":     int(fields.get("pr_number", 0)),
                        "author":        fields.get("author", ""),
                        "risk_score":    float(fields.get("risk_score", 0)),
                        "risk_level":    fields.get("risk_level", ""),
                        "files_changed": int(fields.get("files_changed", 0)),
                        "lines_added":   int(fields.get("lines_added", 0)),
                        "lines_removed": int(fields.get("lines_removed", 0)),
                        "repo_owner":    fields.get("repo_owner", ""),
                        "repo_name":     fields.get("repo_name", ""),
                    }

                    data = json.dumps(payload)
                    manager.broadcast(data)

                    logger.info(
                        "Broadcasted PR #%s (%s) to %d client(s)",
                        fields.get("pr_number"),
                        fields.get("risk_level"),
                        manager.client_count,
                    )

        except asyncio.CancelledError:
            logger.info("SSE broadcaster shutting down")
            break
        except Exception as exc:
            logger.error("SSE broadcaster error: %s", exc)
            await asyncio.sleep(2)   # brief pause before retrying
