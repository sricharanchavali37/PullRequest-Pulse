"""
main.py — Phase-2 Worker Entrypoint

Run with:
    cd services/worker
    python app/main.py
"""

import asyncio

from app.worker import run_worker


if __name__ == "__main__":
    try:
        asyncio.run(run_worker())
    except KeyboardInterrupt:
        print("Worker shutting down")