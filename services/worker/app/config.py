import os

# ── Redis connection ──────────────────────────────────────────────────────────
REDIS_HOST: str = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT: int = int(os.getenv("REDIS_PORT", "6379"))
REDIS_URL:  str = f"redis://{REDIS_HOST}:{REDIS_PORT}/0"

# Stream / consumer group identifiers
# These must match exactly what the webhook service writes to.
STREAM_NAME: str = "prpulse:events:raw"
GROUP_NAME:  str = "prpulse-analysis-workers"

# ── GitHub API ────────────────────────────────────────────────────────────────
GITHUB_TOKEN: str = os.getenv("GITHUB_TOKEN", "")
GITHUB_OWNER: str = os.getenv("GITHUB_OWNER", "")
GITHUB_REPO:  str = os.getenv("GITHUB_REPO",  "")

GITHUB_API_BASE:    str = "https://api.github.com"
GITHUB_API_TIMEOUT: int = 10    # seconds per request
GITHUB_MAX_RETRIES: int = 3     # attempts before giving up


# ── Startup validation ────────────────────────────────────────────────────────

def validate_config() -> None:
    """
    Validate that all required environment variables are set.
    Called once at worker startup before any processing begins.

    Raises RuntimeError with a descriptive message on the first
    missing variable so the operator knows exactly what to fix.
    """
    required = {
        "GITHUB_TOKEN": GITHUB_TOKEN,
        "GITHUB_OWNER": GITHUB_OWNER,
        "GITHUB_REPO":  GITHUB_REPO,
    }
    for name, value in required.items():
        if not value:
            raise RuntimeError(
                f"{name} not set. "
                f"Export it before starting the worker:\n"
                f"  Linux/Mac: export {name}=your_value\n"
                f"  Windows:   set {name}=your_value"
            )