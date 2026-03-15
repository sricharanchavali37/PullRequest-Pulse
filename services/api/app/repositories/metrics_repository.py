"""
repositories/metrics_repository.py — Aggregation queries for repo metrics

repo_id is now a str (stable hash).  All other logic unchanged.
"""

import logging

import asyncpg

from app.config import HIGH_RISK_THRESHOLD

logger = logging.getLogger(__name__)


async def fetch_repo_metrics(
    conn:       asyncpg.Connection,
    repo_owner: str,
    repo_name:  str,
    repo_id:    str,                    # str, not int
) -> dict:
    """Compute all repository metrics in a single aggregation query."""
    row = await conn.fetchrow(
        """
        SELECT
            COUNT(pr.id)                                    AS total_pull_requests,

            COALESCE(
                AVG(a.lines_added + a.lines_removed),
                0.0
            )                                               AS average_pr_size,

            COALESCE(AVG(a.risk_score), 0.0)                AS average_risk_score,

            COUNT(a.id) FILTER (
                WHERE a.risk_score >= $3
            )                                               AS high_risk_pr_count,

            -- merged_at not yet in schema; 0 until column is added
            0                                               AS merged_pr_count

        FROM pull_requests pr
        LEFT JOIN pr_analysis a
            ON a.pr_number = pr.pr_number
        WHERE
            pr.repo_owner = $1
            AND pr.repo_name = $2
        """,
        repo_owner, repo_name, HIGH_RISK_THRESHOLD,
    )

    if row is None:
        return {
            "repository_id":       repo_id,
            "total_pull_requests": 0,
            "average_pr_size":     0.0,
            "average_risk_score":  0.0,
            "high_risk_pr_count":  0,
            "merged_pr_count":     0,
        }

    logger.debug(
        "fetch_repo_metrics(%s/%s) total=%d avg_size=%.1f avg_risk=%.2f",
        repo_owner, repo_name,
        row["total_pull_requests"],
        row["average_pr_size"],
        row["average_risk_score"],
    )

    return {
        "repository_id":       repo_id,
        "total_pull_requests": row["total_pull_requests"]  or 0,
        "average_pr_size":     round(float(row["average_pr_size"]  or 0.0), 2),
        "average_risk_score":  round(float(row["average_risk_score"] or 0.0), 2),
        "high_risk_pr_count":  row["high_risk_pr_count"]   or 0,
        "merged_pr_count":     row["merged_pr_count"]      or 0,
    }