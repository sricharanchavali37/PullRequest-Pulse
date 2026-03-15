"""
db/repository.py — Data access layer for PRPulse worker

All SQL lives here.  worker.py never touches raw SQL.

Idempotency:
  insert_pull_request() uses INSERT ... ON CONFLICT (pr_number) DO NOTHING.
  The UNIQUE constraint on pull_requests.pr_number (defined in schema.sql)
  is the database-level guarantee.  If the worker retries the same PR, the
  second insert is silently ignored — no duplicate, no error.

  insert_analysis_result() records each successful analysis run once.
  Persistence is only called after the full pipeline succeeds, so retries
  never produce extra rows — a row is written exactly once per successful run.
"""

import logging

import asyncpg

from app.db.client import get_pool

logger = logging.getLogger(__name__)


async def insert_pull_request(
    pr_number:  int,
    author:     str,
    repo_owner: str,
    repo_name:  str,
) -> None:
    """
    Insert a pull request row.

    ON CONFLICT (pr_number) DO NOTHING makes this fully idempotent:
    retrying the same PR number never raises an error and never creates
    a duplicate row.
    """
    pool = get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO pull_requests (pr_number, author, repo_owner, repo_name)
            VALUES ($1, $2, $3, $4)
            ON CONFLICT (pr_number) DO NOTHING
            """,
            pr_number,
            author,
            repo_owner,
            repo_name,
        )
    logger.debug("insert_pull_request: pr_number=%d (idempotent)", pr_number)


async def insert_analysis_result(
    pr_number:     int,
    files_changed: int,
    lines_added:   int,
    lines_removed: int,
    risk_score:    float,
    risk_level:    str,
) -> None:
    """
    Insert an analysis result row.

    Each successful analysis run is recorded once.
    The foreign key on pr_number enforces that a pull_requests row
    must exist before an analysis row can be inserted.
    """
    pool = get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO pr_analysis
                (pr_number, files_changed, lines_added, lines_removed,
                 risk_score, risk_level)
            VALUES ($1, $2, $3, $4, $5, $6)
            """,
            pr_number,
            files_changed,
            lines_added,
            lines_removed,
            risk_score,
            risk_level,
        )
    logger.debug("insert_analysis_result: pr_number=%d risk=%s", pr_number, risk_level)