import os
from dotenv import load_dotenv

load_dotenv()

# ── Redis ─────────────────────────────────────────────────────────────────────
REDIS_HOST: str = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT: int = int(os.getenv("REDIS_PORT", "6379"))
REDIS_URL:  str = f"redis://{REDIS_HOST}:{REDIS_PORT}/0"

# ── Redis stream name ─────────────────────────────────────────────────────────
# Must match the stream name the worker reads from (STREAM_NAME in worker/config.py)
STREAM_NAME: str = "prpulse:events:raw"

# ── GitHub webhook secret ─────────────────────────────────────────────────────
# Set this in your .env file to the same secret you entered in GitHub App settings.
# GitHub sends a HMAC-SHA256 signature in every webhook request using this secret.
# If left empty, signature verification is skipped (acceptable for local testing).
GITHUB_WEBHOOK_SECRET: str = os.getenv("GITHUB_WEBHOOK_SECRET", "")