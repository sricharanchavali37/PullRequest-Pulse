"""
worker.py — Phase-2 Worker

Responsibilities:
  1. Connect to Redis
  2. Ensure the consumer group exists (idempotent)
  3. Run an infinite async loop:
       a. Read one message from the stream via XREADGROUP
       b. Extract event_type and pr_number
       c. Log the event to the console
       d. Acknowledge the message with XACK

This module contains no GitHub API calls, no database writes,
and no risk scoring — those belong to later phases.
"""

import asyncio
import socket

import redis.asyncio as aioredis
from redis.exceptions import ResponseError

from app.config import REDIS_URL, STREAM_NAME, GROUP_NAME


def _consumer_name() -> str:
    """
    Unique name for this consumer within the group.
    Using the hostname means multiple worker processes on different
    machines can join the same group without name collisions.
    """
    return f"worker-{socket.gethostname()}"


async def _ensure_consumer_group(client: aioredis.Redis) -> None:
    """
    Creates the consumer group if it does not already exist.

    MKSTREAM creates the stream itself if it does not yet exist —
    safe to call even before the webhook service has written anything.

    If the group already exists Redis raises BUSYGROUP. We catch that
    specific error and continue — it is not a problem.
    """
    try:
        await client.xgroup_create(
            name     = STREAM_NAME,
            groupname= GROUP_NAME,
            id       = "$",        # only deliver messages arriving from now on
            mkstream = True,       # create the stream key if absent
        )
        print(f"Consumer group '{GROUP_NAME}' created on stream '{STREAM_NAME}'")
    except ResponseError as exc:
        if "BUSYGROUP" in str(exc):
            print(f"Consumer group '{GROUP_NAME}' already exists — continuing")
        else:
            raise


def _process_event(redis_message_id: str, fields: dict) -> None:
    """
    Phase-2 processing: extract fields and print them.

    redis_message_id — the stream entry ID e.g. "1704067200000-0"
    fields           — dict of field names to values, all strings
                       e.g. {"event_type": "pr.opened", "pr_number": "10"}

    Output format matches the Phase-2 success criteria exactly.
    """
    event_type = fields.get("event_type", "unknown")
    pr_number  = fields.get("pr_number",  "unknown")

    print("")
    print("Processing PR event")
    print(f"PR number: {pr_number}")
    print(f"Event type: {event_type}")
    print(f"Message ID: {redis_message_id}")


async def run_worker() -> None:
    """
    Main worker loop.

    Connects to Redis, ensures the consumer group exists, then enters
    an infinite loop reading and acknowledging messages.

    BLOCK 5000 means XREADGROUP waits up to 5 seconds for a new message
    before returning an empty result. The loop then immediately retries.
    This avoids a busy-wait while still reacting to new messages within
    5 seconds of arrival.
    """
    consumer = _consumer_name()

    print("Worker starting")

    client = await aioredis.from_url(
        REDIS_URL,
        decode_responses=True,   # return str, not bytes
    )

    # Verify connection before entering the loop
    await client.ping()
    print("Redis connection established")
    print("")
    print(f"Stream: {STREAM_NAME}")
    print(f"Consumer group: {GROUP_NAME}")
    print(f"Consumer name: {consumer}")

    await _ensure_consumer_group(client)

    print("")
    print("Listening to Redis stream...")

    while True:
        # XREADGROUP with ">" delivers only messages not yet delivered
        # to any consumer in this group — the standard production pattern.
        #
        # COUNT 1 — process one message per iteration so each event is
        # acknowledged before the next is read. Keeps the logic simple
        # for Phase-2 and prevents lost events if the process crashes.
        results = await client.xreadgroup(
            groupname    = GROUP_NAME,
            consumername = consumer,
            streams      = {STREAM_NAME: ">"},
            count        = 1,
            block        = 5000,   # milliseconds — 5 second wait
        )

        # results is None or empty when the block timeout expires
        # with no new messages. Sleep briefly to prevent a tight CPU
        # loop, then wait for the next message.
        if not results:
            await asyncio.sleep(0.1)
            continue

        # results shape:
        #   [ (stream_name, [(message_id, {field: value, ...})]) ]
        for _stream_name, messages in results:
            for redis_message_id, fields in messages:

                _process_event(redis_message_id, fields)

                # XACK removes the message from the Pending Entries List.
                # Only called after processing completes successfully.
                # If the process crashes before this line the message
                # stays in the PEL and can be reclaimed later (Phase-4).
                await client.xack(STREAM_NAME, GROUP_NAME, redis_message_id)

                print("Event acknowledged")