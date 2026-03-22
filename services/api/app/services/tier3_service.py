"""
services/tier3_service.py — Business logic for Tier-3 endpoints

Follows the same pattern as metrics_service.py:
  - Validate repo exists (raises 404 if not)
  - Call the repository layer
  - Return the Pydantic response model

No SQL here. No HTTP concerns in the repository layer.
"""

import logging

import asyncpg

from app.repositories.tier3_repository import (
    fetch_cycle_time,
    fetch_reviewer_stats,
    fetch_weekly_trends,
)
from app.schemas.tier3_schema import (
    CycleTimeMetrics,
    CycleTimeResponse,
    ReviewerStats,
    ReviewerLeaderboardResponse,
    WeeklySnapshot,
    WeeklyTrendResponse,
)
from app.services.repo_service import get_repo_by_id_or_404

logger = logging.getLogger(__name__)


async def get_cycle_time(
    conn:        asyncpg.Connection,
    repo_id:     str,
    period_days: int = 30,
) -> CycleTimeResponse:
    """
    Cycle time statistics for merged PRs in the last N days.
    Raises 404 if the repo does not exist.
    """
    repo = await get_repo_by_id_or_404(conn, repo_id)
    data = await fetch_cycle_time(
        conn        = conn,
        repo_owner  = repo["owner"],
        repo_name   = repo["name"],
        period_days = period_days,
    )

    metrics = CycleTimeMetrics(
        repository_id = repo_id,
        avg_hours     = data["avg_hours"],
        median_hours  = data["median_hours"],
        min_hours     = data["min_hours"],
        max_hours     = data["max_hours"],
        sample_size   = data["sample_size"],
        period_days   = data["period_days"],
    )

    return CycleTimeResponse(
        repository_id = repo_id,
        cycle_time    = metrics,
    )


async def get_reviewer_leaderboard(
    conn:        asyncpg.Connection,
    repo_id:     str,
    period_days: int = 30,
) -> ReviewerLeaderboardResponse:
    """
    Per-reviewer stats sorted by total reviews descending.
    Raises 404 if the repo does not exist.
    """
    repo = await get_repo_by_id_or_404(conn, repo_id)
    rows = await fetch_reviewer_stats(
        conn        = conn,
        repo_owner  = repo["owner"],
        repo_name   = repo["name"],
        period_days = period_days,
    )

    reviewers = [ReviewerStats(**row) for row in rows]

    return ReviewerLeaderboardResponse(
        repository_id = repo_id,
        period_days   = period_days,
        reviewers     = reviewers,
    )


async def get_weekly_trends(
    conn:    asyncpg.Connection,
    repo_id: str,
    weeks:   int = 12,
) -> WeeklyTrendResponse:
    """
    Weekly aggregated metrics for the last N weeks.
    Raises 404 if the repo does not exist.
    """
    repo = await get_repo_by_id_or_404(conn, repo_id)
    rows = await fetch_weekly_trends(
        conn       = conn,
        repo_owner = repo["owner"],
        repo_name  = repo["name"],
        weeks      = weeks,
    )

    snapshots = [WeeklySnapshot(**row) for row in rows]

    return WeeklyTrendResponse(
        repository_id = repo_id,
        weeks         = snapshots,
    )
