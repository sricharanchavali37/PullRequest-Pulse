import os

# ── Database ──────────────────────────────────────────────────────────────────
DATABASE_URL: str = os.getenv(
    "DATABASE_URL",
    "postgresql://postgres:postgres@localhost:5432/prpulse",
)

# ── Redis (for SSE broadcaster) ───────────────────────────────────────────────
REDIS_HOST: str = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT: int = int(os.getenv("REDIS_PORT", "6379"))

# ── API settings ──────────────────────────────────────────────────────────────
API_HOST:  str = os.getenv("API_HOST", "0.0.0.0")
API_PORT:  int = int(os.getenv("API_PORT", "8000"))
LOG_LEVEL: str = os.getenv("LOG_LEVEL", "info")

# ── Pagination limits ─────────────────────────────────────────────────────────
PAGINATION_DEFAULT_LIMIT: int = 50
PAGINATION_MAX_LIMIT:     int = 200

# ── Risk threshold ────────────────────────────────────────────────────────────
HIGH_RISK_THRESHOLD: float = 7.0
