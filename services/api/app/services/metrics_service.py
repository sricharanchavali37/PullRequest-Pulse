"""
services/metrics_service.py — Business logic for metrics and analytics

repo_id is now a str (stable hash) throughout.
"""

import logging

import asyncpg

from app.repositories.metrics_repository  import fetch_repo_metrics
from app.repositories.analytics_repository import (
    fetch_risk_distribution,
    fetch_review_performance,
)
from app.schemas.metrics_schema import (
    RepoMetricsResponse,
    RiskDistributionResponse,
    ReviewPerformanceResponse,
)
from app.services.repo_service import get_repo_by_id_or_404

logger = logging.getLogger(__name__)


async def get_repo_metrics(
    conn:    asyncpg.Connection,
    repo_id: str,
) -> RepoMetricsResponse:
    """Aggregated analytics. Raises 404 if repo not found."""
    repo    = await get_repo_by_id_or_404(conn, repo_id)
    metrics = await fetch_repo_metrics(
        conn       = conn,
        repo_owner = repo["owner"],
        repo_name  = repo["name"],
        repo_id    = repo_id,
    )
    return RepoMetricsResponse(**metrics)


async def get_risk_distribution(
    conn:    asyncpg.Connection,
    repo_id: str,
) -> RiskDistributionResponse:
    """PR counts by risk level. Raises 404 if repo not found."""
    repo = await get_repo_by_id_or_404(conn, repo_id)
    dist = await fetch_risk_distribution(
        conn       = conn,
        repo_owner = repo["owner"],
        repo_name  = repo["name"],
    )
    return RiskDistributionResponse(
        repository_id = repo_id,
        distribution  = dist,
    )


async def get_review_performance(
    conn:    asyncpg.Connection,
    repo_id: str,
) -> ReviewPerformanceResponse:
    """Aggregated review metrics. Raises 404 if repo not found."""
    repo    = await get_repo_by_id_or_404(conn, repo_id)
    metrics = await fetch_review_performance(
        conn       = conn,
        repo_owner = repo["owner"],
        repo_name  = repo["name"],
    )
    return ReviewPerformanceResponse(
        repository_id = repo_id,
        metrics       = metrics,
    )