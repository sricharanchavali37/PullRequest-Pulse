"""
main.py — Phase-4 Worker Entrypoint

Run with:
    cd services/worker
    python app/main.py

Or with module syntax:
    python -m app.main
"""

import asyncio
import logging

from app.worker import run_worker

logger = logging.getLogger(__name__)


if __name__ == "__main__":
    try:
        asyncio.run(run_worker())
    except KeyboardInterrupt:
        logger.info("Worker shutting down")