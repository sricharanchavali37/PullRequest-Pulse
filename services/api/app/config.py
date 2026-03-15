"""
config.py — API service configuration

All values come from environment variables.
Defaults are provided so the service works out-of-the-box with
docker-compose without extra setup.
"""

import os

# ── Database ──────────────────────────────────────────────────────────────────
DATABASE_URL: str = os.getenv(
    "DATABASE_URL",
    "postgresql://postgres:postgres@localhost:5432/prpulse",
)

# ── API settings ──────────────────────────────────────────────────────────────
API_HOST:  str = os.getenv("API_HOST", "0.0.0.0")
API_PORT:  int = int(os.getenv("API_PORT", "8000"))
LOG_LEVEL: str = os.getenv("LOG_LEVEL", "info")

# ── Pagination limits ─────────────────────────────────────────────────────────
PAGINATION_DEFAULT_LIMIT: int = 50
PAGINATION_MAX_LIMIT:     int = 200

# ── Risk threshold ────────────────────────────────────────────────────────────
# A pull request is considered high-risk if risk_score >= this value
HIGH_RISK_THRESHOLD: float = 7.0