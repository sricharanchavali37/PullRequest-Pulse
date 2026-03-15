from dotenv import load_dotenv
load_dotenv()

import os

# ── Redis connection ──────────────────────────────────────────────────────────
REDIS_HOST: str = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT: int = int(os.getenv("REDIS_PORT", "6379"))
REDIS_URL:  str = f"redis://{REDIS_HOST}:{REDIS_PORT}/0"

# ── Redis stream / consumer group identifiers ─────────────────────────────────
# All workers reference these constants — no inline strings anywhere.
STREAM_NAME:        str = "prpulse:events:raw"      # primary ingest stream
FAILED_STREAM_NAME: str = "prpulse:events:failed"   # dead letter queue
GROUP_NAME:         str = "prpulse-analysis-workers"

# ── PEL recovery schedule ─────────────────────────────────────────────────────
# Recovery task runs every RECOVERY_INTERVAL_SECONDS seconds.
# Any message idle in the PEL for more than RECOVERY_IDLE_MS milliseconds
# is reclaimed and reprocessed.
RECOVERY_INTERVAL_SECONDS: int = 30
RECOVERY_IDLE_MS:          int = 60_000   # 60 seconds
RECOVERY_BATCH_SIZE:       int = 10

# ── GitHub API ────────────────────────────────────────────────────────────────
GITHUB_TOKEN: str = os.getenv("GITHUB_TOKEN", "")
GITHUB_OWNER: str = os.getenv("GITHUB_OWNER", "")
GITHUB_REPO:  str = os.getenv("GITHUB_REPO",  "")

GITHUB_API_BASE:    str = "https://api.github.com"
GITHUB_API_TIMEOUT: int = 10
GITHUB_MAX_RETRIES: int = 3

# ── Database ──────────────────────────────────────────────────────────────────
DATABASE_URL: str = os.getenv(
    "DATABASE_URL",
    "postgresql://postgres:postgres@localhost:5432/prpulse",
)

# ── Retry backoff schedule (seconds) ─────────────────────────────────────────
# Index 0 = after attempt 1 fails, index 1 = after attempt 2 fails, etc.
RETRY_BACKOFF: tuple[int, ...] = (1, 2, 4)
MAX_RETRIES:   int             = len(RETRY_BACKOFF)


# ── Startup validation ────────────────────────────────────────────────────────

def validate_config() -> None:
    """
    Validate all required environment variables at startup.
    Raises RuntimeError immediately on the first missing value.
    """
    required = {
        "GITHUB_TOKEN": GITHUB_TOKEN,
        "GITHUB_OWNER": GITHUB_OWNER,
        "GITHUB_REPO":  GITHUB_REPO,
        "DATABASE_URL": DATABASE_URL,
    }
    for name, value in required.items():
        if not value:
            raise RuntimeError(
                f"{name} is not set. "
                f"Set it before starting the worker:\n"
                f"  Linux/Mac:  export {name}=<value>\n"
                f"  Windows:    set    {name}=<value>"
            )