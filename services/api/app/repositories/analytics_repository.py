"""
repositories/analytics_repository.py — SQL for the two analytics endpoints

Risk distribution:
  Groups pull requests by normalised risk_level and counts each bucket.
  Returns a RiskDistribution model — named fields, always present.

Review performance:
  Computes average_pr_size, average_risk_score, total_pull_requests
  in a single aggregation query.  Returns a ReviewPerformanceMetrics model.

Both queries:
  - Single SQL round-trip (no N+1)
  - Scoped to the given owner/name pair
  - Return zero-value models when no data exists

Logging:
  Debug logs emit only counts and rounded aggregates — never raw row
  data — so repository content does not appear in server logs.
"""

import logging

import asyncpg

from app.schemas.metrics_schema import RiskDistribution, ReviewPerformanceMetrics

logger = logging.getLogger(__name__)


async def fetch_risk_distribution(
    conn:       asyncpg.Connection,
    repo_owner: str,
    repo_name:  str,
) -> RiskDistribution:
    """
    Return PR counts grouped by risk_level for the given repository.

    LOWER(risk_level) normalises casing so 'HIGH', 'High', and 'high'
    all land in the same bucket.

    PRs with no analysis row (LEFT JOIN miss) map to 'unknown' via
    COALESCE so no PRs are silently dropped from the count.
    """
    rows = await conn.fetch(
        """
        SELECT
            COALESCE(LOWER(a.risk_level), 'unknown') AS risk_level,
            COUNT(*)                                  AS pr_count
        FROM pull_requests pr
        LEFT JOIN pr_analysis a
            ON a.pr_number = pr.pr_number
        WHERE
            pr.repo_owner = $1
            AND pr.repo_name = $2
        GROUP BY COALESCE(LOWER(a.risk_level), 'unknown')
        ORDER BY risk_level
        """,
        repo_owner, repo_name,
    )

    # Collect raw counts from query result
    counts: dict[str, int] = {}
    for row in rows:
        counts[row["risk_level"]] = row["pr_count"]

    dist = RiskDistribution(
        low     = counts.get("low",     0),
        medium  = counts.get("medium",  0),
        high    = counts.get("high",    0),
        unknown = counts.get("unknown", 0),
    )

    # Log counts only — no PR content, no risk level values from data
    logger.debug(
        "fetch_risk_distribution(%s/%s) — total PRs counted: %d",
        repo_owner, repo_name,
        dist.low + dist.medium + dist.high + dist.unknown,
    )
    return dist


async def fetch_review_performance(
    conn:       asyncpg.Connection,
    repo_owner: str,
    repo_name:  str,
) -> ReviewPerformanceMetrics:
    """
    Return aggregated review-performance metrics for the given repository.

    Metrics:
      average_pr_size      — AVG(lines_added + lines_removed)
      average_risk_score   — AVG(risk_score)
      total_pull_requests  — COUNT of all PRs in the repo
    """
    row = await conn.fetchrow(
        """
        SELECT
            COALESCE(AVG(a.lines_added + a.lines_removed), 0.0) AS average_pr_size,
            COALESCE(AVG(a.risk_score), 0.0)                    AS average_risk_score,
            COUNT(pr.id)                                        AS total_pull_requests
        FROM pull_requests pr
        LEFT JOIN pr_analysis a
            ON a.pr_number = pr.pr_number
        WHERE
            pr.repo_owner = $1
            AND pr.repo_name = $2
        """,
        repo_owner, repo_name,
    )

    if row is None:
        return ReviewPerformanceMetrics()

    metrics = ReviewPerformanceMetrics(
        average_pr_size     = round(float(row["average_pr_size"]    or 0.0), 2),
        average_risk_score  = round(float(row["average_risk_score"] or 0.0), 2),
        total_pull_requests = row["total_pull_requests"] or 0,
    )

    # Log totals only — no individual PR data exposed in logs
    logger.debug(
        "fetch_review_performance(%s/%s) — %d PRs, avg_size=%.1f",
        repo_owner, repo_name,
        metrics.total_pull_requests,
        metrics.average_pr_size,
    )
    return metrics