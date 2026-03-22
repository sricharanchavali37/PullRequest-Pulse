"""
api/tier3.py — Tier-3 analytics endpoints

GET /repos/{repo_id}/cycle-time
    Merge time statistics — avg, median, min, max over the last N days.
    Tells you: how fast does code get shipped after a PR is opened?

GET /repos/{repo_id}/reviewers
    Reviewer leaderboard — who reviews most, who responds fastest,
    who approves vs requests changes.
    Tells you: who carries the review load and how responsive are they?

GET /repos/{repo_id}/trends
    Weekly aggregated metrics for the last N weeks.
    Tells you: is code quality improving or degrading over time?

All routes follow the same pattern as the existing endpoints:
  route handler → service layer → repository layer → SQL
  No SQL in this file. No business logic in this file.
"""

import logging
from typing import Annotated

import asyncpg
from fastapi import APIRouter, Depends, Query

from app.db.database import get_db
from app.schemas.tier3_schema import (
    CycleTimeResponse,
    ReviewerLeaderboardResponse,
    WeeklyTrendResponse,
)
from app.services.tier3_service import (
    get_cycle_time,
    get_reviewer_leaderboard,
    get_weekly_trends,
)

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get(
    "/repos/{repo_id}/cycle-time",
    response_model = CycleTimeResponse,
    summary        = "PR merge cycle time statistics",
    responses      = {404: {"description": "Repository not found"}},
)
async def cycle_time(
    repo_id:     str,
    period_days: Annotated[int, Query(ge=1, le=365, description="Days to look back")] = 30,
    conn:        asyncpg.Connection = Depends(get_db),
) -> CycleTimeResponse:
    """
    Return cycle time statistics for merged PRs in the last N days.

    - **avg_hours** — mean time from PR open to merge
    - **median_hours** — 50th percentile (less skewed by outliers)
    - **min_hours** — fastest merge
    - **max_hours** — slowest merge
    - **sample_size** — how many merged PRs this covers
    - **period_days** — how far back the query looks

    All values are null when no merged PRs exist in the period.
    """
    return await get_cycle_time(conn, repo_id, period_days)


@router.get(
    "/repos/{repo_id}/reviewers",
    response_model = ReviewerLeaderboardResponse,
    summary        = "Reviewer leaderboard",
    responses      = {404: {"description": "Repository not found"}},
)
async def reviewer_leaderboard(
    repo_id:     str,
    period_days: Annotated[int, Query(ge=1, le=365, description="Days to look back")] = 30,
    conn:        asyncpg.Connection = Depends(get_db),
) -> ReviewerLeaderboardResponse:
    """
    Return per-reviewer analytics sorted by total reviews descending.

    Per reviewer:
    - **total_reviews** — number of reviews submitted
    - **avg_response_hours** — average hours from PR open to their review
    - **approvals** — count of approved reviews
    - **change_requests** — count of changes_requested reviews
    - **comments** — count of comment-only reviews
    - **approval_rate_pct** — approvals / total * 100

    Empty list when no reviews exist in the period.
    """
    return await get_reviewer_leaderboard(conn, repo_id, period_days)


@router.get(
    "/repos/{repo_id}/trends",
    response_model = WeeklyTrendResponse,
    summary        = "Weekly engineering health trends",
    responses      = {404: {"description": "Repository not found"}},
)
async def weekly_trends(
    repo_id: str,
    weeks:   Annotated[int, Query(ge=1, le=52, description="Number of weeks to return")] = 12,
    conn:    asyncpg.Connection = Depends(get_db),
) -> WeeklyTrendResponse:
    """
    Return weekly aggregated metrics for the last N weeks.

    Per week (Monday → Sunday):
    - **prs_opened** — PRs opened this week
    - **prs_merged** — PRs merged this week
    - **avg_risk_score** — mean risk score of PRs opened this week
    - **avg_cycle_time_hours** — mean merge time for PRs merged this week
    - **avg_review_latency_hours** — mean time to first review
    - **avg_pr_size** — mean lines changed
    - **high_risk_count** — PRs scored HIGH this week

    Weeks are ordered oldest → newest.
    Returns pre-computed snapshots if available, live computation otherwise.
    """
    return await get_weekly_trends(conn, repo_id, weeks)
