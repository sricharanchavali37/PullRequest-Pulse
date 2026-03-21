"""
sse/connection_manager.py — Tracks connected SSE clients.

Each client that opens GET /events/stream gets registered here
with their own asyncio.Queue. When the broadcaster receives a new
notification from Redis, it puts the event into every client's queue.
The SSE endpoint reads from its own queue and streams to the browser.

Why asyncio.Queue per client:
  Each client consumes at their own pace. A slow or disconnected client
  doesn't block other clients — we just drop events for that client if
  their queue is full (they catch up on reconnect via the REST API).
"""

import asyncio
import logging
from typing import Set

logger = logging.getLogger(__name__)


class ConnectionManager:
    def __init__(self) -> None:
        self._clients: Set[asyncio.Queue] = set()

    def add(self, queue: asyncio.Queue) -> None:
        self._clients.add(queue)
        logger.info("SSE client connected — total: %d", len(self._clients))

    def remove(self, queue: asyncio.Queue) -> None:
        self._clients.discard(queue)
        logger.info("SSE client disconnected — total: %d", len(self._clients))

    def broadcast(self, data: str) -> None:
        """
        Put a message into every connected client's queue.
        If a client's queue is full (maxsize=50), skip that client.
        They will catch up via the REST API on reconnect.
        """
        dead: list[asyncio.Queue] = []
        for queue in self._clients:
            try:
                queue.put_nowait(data)
            except asyncio.QueueFull:
                logger.warning("SSE client queue full — skipping event for one client")
                dead.append(queue)

        # Remove clients whose queues have been consistently full
        for queue in dead:
            self._clients.discard(queue)

    @property
    def client_count(self) -> int:
        return len(self._clients)


# ── Singleton ─────────────────────────────────────────────────────────────────
# One instance shared across the whole API process.
manager = ConnectionManager()
