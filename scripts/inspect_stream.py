"""
scripts/inspect_stream.py

A simple debug script to inspect what is currently in your Redis streams.
Run this any time you want to see what events are waiting, what failed,
or what the worker has already processed.

Usage (from project root):
    python scripts/inspect_stream.py

Make sure Redis is running before you run this.
"""

import asyncio
import os

import redis.asyncio as aioredis

# ── Config ────────────────────────────────────────────────────────────────────
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))
REDIS_URL  = f"redis://{REDIS_HOST}:{REDIS_PORT}/0"

STREAM_EVENTS_RAW    = "prpulse:events:raw"
STREAM_EVENTS_FAILED = "prpulse:events:failed"
GROUP_NAME           = "prpulse-analysis-workers"


async def main() -> None:
    r = aioredis.from_url(REDIS_URL, decode_responses=True)

    try:
        await r.ping()
    except Exception:
        print("ERROR: Cannot connect to Redis. Is it running?")
        print(f"       Tried: {REDIS_URL}")
        return

    print("=" * 60)
    print("PRPulse — Redis Stream Inspector")
    print("=" * 60)

    # ── Main stream ───────────────────────────────────────────────────────────
    length = await r.xlen(STREAM_EVENTS_RAW)
    print(f"\n[prpulse:events:raw]  total entries: {length}")

    entries = await r.xrevrange(STREAM_EVENTS_RAW, "+", "-", count=5)
    if entries:
        print("  Last 5 entries (newest first):")
        for stream_id, fields in entries:
            print(f"    {stream_id}  →  {fields}")
    else:
        print("  (empty)")

    # ── Pending Entries List ──────────────────────────────────────────────────
    try:
        pending = await r.xpending(STREAM_EVENTS_RAW, GROUP_NAME)
        count = pending.get("pending", 0)
        print(f"\n[PEL — messages in progress]  count: {count}")
        if count == 0:
            print("  (none — all messages have been acknowledged)")
    except Exception:
        print("\n[PEL]  consumer group not created yet (worker hasn't started)")

    # ── Dead Letter Queue ─────────────────────────────────────────────────────
    dlq_length = await r.xlen(STREAM_EVENTS_FAILED)
    print(f"\n[prpulse:events:failed — DLQ]  total entries: {dlq_length}")

    dlq_entries = await r.xrange(STREAM_EVENTS_FAILED, "-", "+")
    if dlq_entries:
        print("  Failed events:")
        for stream_id, fields in dlq_entries:
            print(f"    {stream_id}  →  {fields}")
    else:
        print("  (empty — no failed events)")

    print("\n" + "=" * 60)
    await r.aclose()


if __name__ == "__main__":
    asyncio.run(main())
