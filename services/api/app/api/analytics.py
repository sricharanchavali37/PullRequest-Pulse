"""
api/analytics.py — Analytics endpoints for dashboards

GET /repos/{repo_id}/risk-distribution
GET /repos/{repo_id}/review-performance

repo_id is a string (stable 8-char hex hash).
Routes delegate entirely to the service layer — no SQL here.
"""

import logging

import asyncpg
from fastapi import APIRouter, Depends

from app.db.database import get_db
from app.schemas.metrics_schema import RiskDistributionResponse, ReviewPerformanceResponse
from app.services.metrics_service import get_risk_distribution, get_review_performance

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get(
    "/repos/{repo_id}/risk-distribution",
    response_model = RiskDistributionResponse,
    summary        = "PR count by risk level",
    responses      = {404: {"description": "Repository not found"}},
)
async def risk_distribution(
    repo_id: str,
    conn:    asyncpg.Connection = Depends(get_db),
) -> RiskDistributionResponse:
    """
    Return how many pull requests fall into each risk bucket.

    Useful for pie / donut charts on engineering dashboards.

    - **low** — PRs with risk_level = 'low'
    - **medium** — PRs with risk_level = 'medium'
    - **high** — PRs with risk_level = 'high'

    Buckets always appear in the response even when the count is 0.
    """
    return await get_risk_distribution(conn, repo_id)


@router.get(
    "/repos/{repo_id}/review-performance",
    response_model = ReviewPerformanceResponse,
    summary        = "Aggregated review performance metrics",
    responses      = {404: {"description": "Repository not found"}},
)
async def review_performance(
    repo_id: str,
    conn:    asyncpg.Connection = Depends(get_db),
) -> ReviewPerformanceResponse:
    """
    Return aggregated metrics useful for understanding review workload.

    - **average_pr_size** — mean (lines_added + lines_removed)
    - **average_risk_score** — mean risk_score across all PRs
    - **total_pull_requests** — total PR count
    """
    return await get_review_performance(conn, repo_id)