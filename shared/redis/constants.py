# shared/redis/constants.py
#
# Every stream name and consumer group name used across the whole project
# lives here. No service ever uses an inline string like "prpulse:events:raw"
# — they all import from here.
#
# Why this matters:
#   If you rename a stream, you change it in ONE place.
#   If you typo a stream name, your editor catches it (it's a variable, not a string).

# ── Streams ───────────────────────────────────────────────────────────────────

STREAM_EVENTS_RAW: str = "prpulse:events:raw"
# The main ingest stream. Webhook writes here. Worker reads from here.

STREAM_EVENTS_FAILED: str = "prpulse:events:failed"
# Dead Letter Queue. Worker writes here after 3 failed retries.

STREAM_NOTIFICATIONS: str = "prpulse:notifications"
# Phase 6: worker writes here after analysis. SSE broadcaster reads from here.

# ── Consumer groups ───────────────────────────────────────────────────────────

GROUP_ANALYSIS_WORKERS: str = "prpulse-analysis-workers"
# The consumer group the worker uses when reading from STREAM_EVENTS_RAW.
