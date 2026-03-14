import os

# Redis connection
REDIS_HOST: str = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT: int = int(os.getenv("REDIS_PORT", "6379"))
REDIS_URL:  str = f"redis://{REDIS_HOST}:{REDIS_PORT}/0"

# Stream / consumer group identifiers
# These must match exactly what the webhook service writes to.
STREAM_NAME:    str = "prpulse:events:raw"
GROUP_NAME:     str = "prpulse-analysis-workers"