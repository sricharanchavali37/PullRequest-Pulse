"""
repositories/tier3_repository.py — SQL queries for Tier-3 endpoints

Three query functions:
  fetch_cycle_time        — avg/median/min/max merge time
  fetch_reviewer_stats    — per-reviewer leaderboard
  fetch_weekly_trends     — pre-aggregated weekly snapshots

All queries:
  - Single SQL round-trip (no N+1 loops)
  - Scoped to repo_owner + repo_name pair
  - Return safe defaults when no data exists
  - Use PERCENTILE_CONT for median (PostgreSQL ordered-set aggregate)
"""

import logging
from datetime import date

import asyncpg

logger = logging.getLogger(__name__)


async def fetch_cycle_time(
    conn:        asyncpg.Connection,
    repo_owner:  str,
    repo_name:   str,
    period_days: int = 30,
) -> dict:
    """
    Compute cycle time statistics for merged PRs in the last N days.

    cycle_time_hours is stored on the pull_requests row at merge time
    (computed by the worker in mark_pr_merged). This query just aggregates
    that pre-computed float — no timestamp arithmetic at read time.

    PERCENTILE_CONT(0.5) is PostgreSQL's median aggregate.
    It requires an ordered-set syntax: WITHIN GROUP (ORDER BY ...).
    """
    row = await conn.fetchrow(
        """
        SELECT
            COUNT(*)                             AS sample_size,
            AVG(cycle_time_hours)                AS avg_hours,
            PERCENTILE_CONT(0.5)
                WITHIN GROUP (ORDER BY cycle_time_hours)
                                                 AS median_hours,
            MIN(cycle_time_hours)                AS min_hours,
            MAX(cycle_time_hours)                AS max_hours
        FROM pull_requests
        WHERE
            repo_owner           = $1
            AND repo_name        = $2
            AND state            = 'merged'
            AND merged_at        IS NOT NULL
            AND cycle_time_hours IS NOT NULL
            AND merged_at        >= NOW() - ($3 * INTERVAL '1 day')
        """,
        repo_owner, repo_name, period_days,
    )

    if row is None or row["sample_size"] == 0:
        return {
            "sample_size":  0,
            "avg_hours":    None,
            "median_hours": None,
            "min_hours":    None,
            "max_hours":    None,
            "period_days":  period_days,
        }

    logger.debug(
        "fetch_cycle_time(%s/%s, %dd) — %d merged PRs, avg=%.2fh",
        repo_owner, repo_name, period_days,
        row["sample_size"], row["avg_hours"] or 0,
    )

    return {
        "sample_size":  int(row["sample_size"]),
        "avg_hours":    float(row["avg_hours"])    if row["avg_hours"]    is not None else None,
        "median_hours": float(row["median_hours"]) if row["median_hours"] is not None else None,
        "min_hours":    float(row["min_hours"])    if row["min_hours"]    is not None else None,
        "max_hours":    float(row["max_hours"])    if row["max_hours"]    is not None else None,
        "period_days":  period_days,
    }


async def fetch_reviewer_stats(
    conn:        asyncpg.Connection,
    repo_owner:  str,
    repo_name:   str,
    period_days: int = 30,
) -> list[dict]:
    """
    Return per-reviewer statistics for the last N days.

    Groups pr_reviews by reviewer and computes:
      - total review count
      - average response time (review_latency_hours stored at insert time)
      - approval / change_request / comment counts
      - approval rate percentage

    NULLIF prevents division-by-zero for approval_rate_pct.
    FILTER (WHERE ...) is PostgreSQL's conditional aggregate — cleaner
    than CASE WHEN inside SUM().
    """
    rows = await conn.fetch(
        """
        SELECT
            r.reviewer,

            COUNT(*)                                          AS total_reviews,

            ROUND(
                COALESCE(AVG(r.review_latency_hours), 0.0)
                ::numeric, 2
            )                                                 AS avg_response_hours,

            COUNT(*) FILTER (WHERE r.state = 'approved')     AS approvals,
            COUNT(*) FILTER (
                WHERE r.state = 'changes_requested'
            )                                                 AS change_requests,
            COUNT(*) FILTER (WHERE r.state = 'commented')    AS comments,

            ROUND(
                COUNT(*) FILTER (WHERE r.state = 'approved')
                * 100.0
                / NULLIF(COUNT(*), 0)
                , 1
            )                                                 AS approval_rate_pct

        FROM pr_reviews r
        WHERE
            r.repo_owner     = $1
            AND r.repo_name  = $2
            AND r.submitted_at >= NOW() - ($3 || ' days')::INTERVAL
        GROUP BY r.reviewer
        ORDER BY total_reviews DESC, r.reviewer
        """,
        repo_owner, repo_name, str(period_days),
    )

    logger.debug(
        "fetch_reviewer_stats(%s/%s, %dd) — %d reviewers",
        repo_owner, repo_name, period_days, len(rows),
    )

    return [
        {
            "reviewer":           row["reviewer"],
            "total_reviews":      int(row["total_reviews"]),
            "avg_response_hours": float(row["avg_response_hours"] or 0.0),
            "approvals":          int(row["approvals"]),
            "change_requests":    int(row["change_requests"]),
            "comments":           int(row["comments"]),
            "approval_rate_pct":  float(row["approval_rate_pct"] or 0.0),
        }
        for row in rows
    ]


async def fetch_weekly_trends(
    conn:       asyncpg.Connection,
    repo_owner: str,
    repo_name:  str,
    weeks:      int = 12,
) -> list[dict]:
    """
    Return weekly snapshots for the last N weeks.

    First checks weekly_snapshots for pre-computed data (written by the
    snapshot job). If no snapshots exist yet, falls back to computing
    them on-the-fly from raw pull_requests data.

    On-the-fly computation:
      DATE_TRUNC('week', created_at) groups PRs by the Monday of their week.
      This is standard PostgreSQL — weeks start on Monday by default.

    Results are ordered oldest → newest so a chart plots left → right.
    """

    # Try pre-computed snapshots first
    snapshot_rows = await conn.fetch(
        """
        SELECT
            week_start::TEXT                  AS week_start,
            prs_opened,
            prs_merged,
            avg_risk_score,
            avg_cycle_time_hours,
            avg_review_latency_hours,
            avg_pr_size,
            high_risk_count
        FROM weekly_snapshots
        WHERE
            repo_owner = $1
            AND repo_name = $2
            AND week_start >= CURRENT_DATE - ($3 * 7)
        ORDER BY week_start ASC
        """,
        repo_owner, repo_name, weeks,
    )

    if snapshot_rows:
        logger.debug(
            "fetch_weekly_trends(%s/%s) — %d snapshots from weekly_snapshots table",
            repo_owner, repo_name, len(snapshot_rows),
        )
        return [dict(row) for row in snapshot_rows]

    # Fall back: compute on the fly from pull_requests
    logger.debug(
        "fetch_weekly_trends(%s/%s) — no snapshots, computing on-the-fly",
        repo_owner, repo_name,
    )

    live_rows = await conn.fetch(
        """
        SELECT
            DATE_TRUNC('week', pr.created_at)::DATE::TEXT   AS week_start,

            COUNT(pr.id)                                     AS prs_opened,

            COUNT(pr.id) FILTER (
                WHERE pr.state = 'merged'
            )                                                AS prs_merged,

            ROUND(
                COALESCE(AVG(a.risk_score), 0.0)::numeric, 2
            )                                                AS avg_risk_score,

            ROUND(
                COALESCE(
                    AVG(pr.cycle_time_hours) FILTER (
                        WHERE pr.cycle_time_hours IS NOT NULL
                    ),
                    0.0
                )::numeric, 2
            )                                                AS avg_cycle_time_hours,

            ROUND(
                COALESCE(
                    AVG(pr.review_latency_hours) FILTER (
                        WHERE pr.review_latency_hours IS NOT NULL
                    ),
                    0.0
                )::numeric, 2
            )                                                AS avg_review_latency_hours,

            ROUND(
                COALESCE(
                    AVG(a.lines_added + a.lines_removed),
                    0.0
                )::numeric, 2
            )                                                AS avg_pr_size,

            COUNT(pr.id) FILTER (
                WHERE a.risk_level = 'HIGH'
            )                                                AS high_risk_count

        FROM pull_requests pr
        LEFT JOIN pr_analysis a ON a.pr_number = pr.pr_number
        WHERE
            pr.repo_owner = $1
            AND pr.repo_name = $2
            AND pr.created_at >= NOW() - ($3 * 7 || ' days')::INTERVAL
        GROUP BY DATE_TRUNC('week', pr.created_at)
        ORDER BY week_start ASC
        """,
        repo_owner, repo_name, weeks,
    )

    return [
        {
            "week_start":               row["week_start"],
            "prs_opened":               int(row["prs_opened"]),
            "prs_merged":               int(row["prs_merged"]),
            "avg_risk_score":           float(row["avg_risk_score"] or 0.0),
            "avg_cycle_time_hours":     float(row["avg_cycle_time_hours"] or 0.0),
            "avg_review_latency_hours": float(row["avg_review_latency_hours"] or 0.0),
            "avg_pr_size":              float(row["avg_pr_size"] or 0.0),
            "high_risk_count":          int(row["high_risk_count"]),
        }
        for row in live_rows
    ]
