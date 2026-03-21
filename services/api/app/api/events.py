"""
api/events.py — Server-Sent Events endpoint.

GET /events/stream

Keeps the HTTP connection open and streams events to the browser
as they arrive. Each event is a JSON object representing an analysed PR.

How SSE works:
  1. Browser calls EventSource("http://localhost:8001/events/stream")
  2. The connection stays open — it never returns a normal response
  3. Every time the server calls `yield`, the browser receives an event
  4. The browser fires a JavaScript "message" event with the data
  5. If the connection drops, EventSource reconnects automatically

SSE frame format (what we send over the wire):
  data: {"pr_number": 1, "risk_level": "LOW", ...}\n\n

The double newline \n\n is what tells the browser "this event is complete".

Heartbeat:
  Every 25 seconds we send a comment line (": heartbeat\n\n").
  This keeps the connection alive through proxies and load balancers
  that close idle connections. The browser ignores comment lines.
"""

import asyncio
import logging
import time

from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from fastapi.requests import Request

from app.sse.connection_manager import manager

logger = logging.getLogger(__name__)
router = APIRouter()

HEARTBEAT_INTERVAL = 25   # seconds


@router.get("/events/stream", summary="Live PR analysis feed (SSE)")
async def events_stream(request: Request) -> StreamingResponse:
    """
    Open a Server-Sent Events connection.

    The browser keeps this connection open and receives a new event
    every time a pull request is analysed. No polling needed.

    Connect from JavaScript:
        const es = new EventSource("http://localhost:8001/events/stream")
        es.onmessage = (e) => console.log(JSON.parse(e.data))
    """

    async def generator():
        queue: asyncio.Queue = asyncio.Queue(maxsize=50)
        manager.add(queue)

        try:
            last_heartbeat = time.monotonic()

            while True:
                # Check if the client has disconnected
                if await request.is_disconnected():
                    break

                try:
                    # Wait up to 1 second for a new event
                    data = await asyncio.wait_for(queue.get(), timeout=1.0)
                    yield f"data: {data}\n\n"

                except asyncio.TimeoutError:
                    # No event arrived — check if we need to send a heartbeat
                    now = time.monotonic()
                    if now - last_heartbeat >= HEARTBEAT_INTERVAL:
                        yield ": heartbeat\n\n"
                        last_heartbeat = now

        except asyncio.CancelledError:
            pass
        finally:
            manager.remove(queue)

    return StreamingResponse(
        generator(),
        media_type = "text/event-stream",
        headers    = {
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",   # tells nginx not to buffer SSE
        },
    )
