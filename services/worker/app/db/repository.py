"""
db/repository.py — Data access layer for PRPulse worker

All SQL lives here. worker.py never touches raw SQL.

Step 2 additions:
  - insert_pull_request: now accepts title, base_branch, head_branch,
    github_pr_id from the real GitHub payload
  - mark_pr_merged: updates state, merged_at, cycle_time_hours
  - mark_pr_closed: updates state, closed_at
  - insert_review: inserts into pr_reviews, updates first_review_at on PR
  - upsert_repository: registers a repo in the repositories table
"""

import logging
from datetime import datetime, timezone

import asyncpg

from app.db.client import get_pool

logger = logging.getLogger(__name__)


async def upsert_repository(
    repo_id:    str,
    owner:      str,
    name:       str,
    github_id:  int | None = None,
) -> None:
    """
    Register a repository. Safe to call on every pr.opened event —
    ON CONFLICT DO NOTHING means existing rows are untouched.
    """
    pool = get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO repositories (id, owner, name, github_id)
            VALUES ($1, $2, $3, $4)
            ON CONFLICT (owner, name) DO NOTHING
            """,
            repo_id, owner, name, github_id,
        )
    logger.debug("upsert_repository: %s/%s id=%s", owner, name, repo_id)


async def insert_pull_request(
    pr_number:   int,
    author:      str,
    repo_owner:  str,
    repo_name:   str,
    title:       str       = "",
    base_branch: str       = "",
    head_branch: str       = "",
    github_pr_id: int | None = None,
) -> None:
    """
    Insert a pull request row.

    ON CONFLICT (pr_number) DO NOTHING makes this fully idempotent.
    If the worker retries the same PR, the second insert is silently ignored.
    """
    pool = get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO pull_requests
                (pr_number, author, repo_owner, repo_name,
                 title, base_branch, head_branch, github_pr_id, state)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, 'open')
            ON CONFLICT (pr_number) DO NOTHING
            """,
            pr_number, author, repo_owner, repo_name,
            title, base_branch, head_branch, github_pr_id,
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
    The FK on pr_number enforces that a pull_requests row must exist first.
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
            pr_number, files_changed, lines_added,
            lines_removed, risk_score, risk_level,
        )
    logger.debug("insert_analysis_result: pr_number=%d risk=%s", pr_number, risk_level)


async def mark_pr_merged(
    pr_number:  int,
    merged_at:  datetime,
) -> None:
    """
    Mark a PR as merged and compute cycle_time_hours.

    cycle_time_hours = (merged_at - created_at) in hours.
    Stored as a float so AVG queries are simple and fast.
    """
    pool = get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """
            UPDATE pull_requests
            SET
                state             = 'merged',
                merged_at         = $2,
                cycle_time_hours  = EXTRACT(
                    EPOCH FROM ($2 - created_at)
                ) / 3600.0
            WHERE pr_number = $1
            """,
            pr_number, merged_at,
        )
    logger.info("mark_pr_merged: pr_number=%d merged_at=%s", pr_number, merged_at)


async def mark_pr_closed(pr_number: int) -> None:
    """
    Mark a PR as closed without merging.
    No cycle_time_hours — it was abandoned, not merged.
    """
    pool = get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """
            UPDATE pull_requests
            SET
                state      = 'closed',
                closed_at  = NOW()
            WHERE pr_number = $1
            """,
            pr_number,
        )
    logger.info("mark_pr_closed: pr_number=%d", pr_number)


async def insert_review(
    pr_number:    int,
    repo_owner:   str,
    repo_name:    str,
    reviewer:     str,
    state:        str,
    submitted_at: datetime,
) -> None:
    """
    Insert a review row and update first_review_at on the PR if this
    is the first review for this PR.

    review_latency_hours = (submitted_at - pr.created_at) in hours.

    Uses a single transaction so the review insert and the PR update
    are atomic — no partial writes if the connection drops between them.
    """
    pool = get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():

            # Fetch the PR's created_at to compute latency
            row = await conn.fetchrow(
                "SELECT created_at FROM pull_requests WHERE pr_number = $1",
                pr_number,
            )

            if row is None:
                # PR not yet in DB (event arrived before pr.opened was processed)
                # Insert review without latency — it will be reprocessed on retry
                logger.warning(
                    "insert_review: pr_number=%d not found — inserting without latency",
                    pr_number,
                )
                latency = None
            else:
                pr_created_at = row["created_at"]
                if pr_created_at.tzinfo is None:
                    pr_created_at = pr_created_at.replace(tzinfo=timezone.utc)
                if submitted_at.tzinfo is None:
                    submitted_at = submitted_at.replace(tzinfo=timezone.utc)

                diff_seconds = (submitted_at - pr_created_at).total_seconds()
                latency = max(0.0, diff_seconds / 3600.0)

            # Insert the review row
            await conn.execute(
                """
                INSERT INTO pr_reviews
                    (pr_number, repo_owner, repo_name,
                     reviewer, state, submitted_at, review_latency_hours)
                VALUES ($1, $2, $3, $4, $5, $6, $7)
                """,
                pr_number, repo_owner, repo_name,
                reviewer, state, submitted_at, latency,
            )

            # Update PR's first_review_at only if not already set
            # and update review_latency_hours to the first review's latency
            await conn.execute(
                """
                UPDATE pull_requests
                SET
                    first_review_at      = COALESCE(first_review_at, $2),
                    review_latency_hours = COALESCE(review_latency_hours, $3)
                WHERE pr_number = $1
                """,
                pr_number, submitted_at, latency,
            )

    logger.info(
        "insert_review: pr_number=%d reviewer=%s state=%s latency=%.2fh",
        pr_number, reviewer, state, latency or 0.0,
    )
