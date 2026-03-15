"""
api/metrics.py — Repository metrics route

GET /repos/{repo_id}/metrics

repo_id is now a str (stable 8-char hex hash).
"""

import logging

import asyncpg
from fastapi import APIRouter, Depends

from app.db.database import get_db
from app.schemas.metrics_schema import RepoMetricsResponse
from app.services.metrics_service import get_repo_metrics

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get(
    "/repos/{repo_id}/metrics",
    response_model = RepoMetricsResponse,
    summary        = "Repository analytics metrics",
    responses      = {404: {"description": "Repository not found"}},
)
async def repo_metrics(
    repo_id: str,                               # str, not int
    conn:    asyncpg.Connection = Depends(get_db),
) -> RepoMetricsResponse:
    """
    Return aggregated analytics for a repository.

    - **total_pull_requests** — total PR count
    - **average_pr_size** — mean (lines_added + lines_removed)
    - **average_risk_score** — mean risk_score
    - **high_risk_pr_count** — PRs with risk_score >= 7
    - **merged_pr_count** — PRs with merged_at set
    """
    return await get_repo_metrics(conn, repo_id)