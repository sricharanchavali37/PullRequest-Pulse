"""
schemas/metrics_schema.py — Pydantic response models for analytics

All analytics responses use repository_id as a str (stable hash).

RiskDistributionResponse uses explicit named fields instead of a dict
so the API contract is self-documenting and dashboards never need to
check for missing keys.  All four fields default to 0.

ReviewPerformanceResponse likewise uses explicit typed fields.
"""

from pydantic import BaseModel


class RepoMetricsResponse(BaseModel):
    """
    Aggregated analytics for a repository.
    Returned by GET /repos/{repo_id}/metrics.
    """
    repository_id:       str           # stable hash ID
    total_pull_requests: int   = 0
    average_pr_size:     float = 0.0   # AVG(lines_added + lines_removed)
    average_risk_score:  float = 0.0
    high_risk_pr_count:  int   = 0     # risk_score >= HIGH_RISK_THRESHOLD
    merged_pr_count:     int   = 0     # PRs with merged_at IS NOT NULL


class RiskDistribution(BaseModel):
    """
    Explicit named buckets for risk level counts.

    Using named fields instead of dict[str, int] means:
      - the contract is visible in /docs
      - dashboards never need to guard against missing keys
      - all four fields always have a value (default 0)

    unknown: PRs that exist but have no analysis row yet
             (still in the worker queue, or analysis failed).
    """
    low:     int = 0
    medium:  int = 0
    high:    int = 0
    unknown: int = 0


class RiskDistributionResponse(BaseModel):
    """
    Returned by GET /repos/{repo_id}/risk-distribution.

    Example:
        {
          "repository_id": "9f7c2e91",
          "distribution": {"low": 42, "medium": 17, "high": 6, "unknown": 0}
        }
    """
    repository_id: str
    distribution:  RiskDistribution


class ReviewPerformanceMetrics(BaseModel):
    """
    Explicit fields for review-performance metrics.

    Using named fields instead of dict[str, float | int] makes the
    contract visible in /docs and removes the need for key-existence
    checks on the client side.
    """
    average_pr_size:     float = 0.0   # AVG(lines_added + lines_removed)
    average_risk_score:  float = 0.0
    total_pull_requests: int   = 0


class ReviewPerformanceResponse(BaseModel):
    """
    Returned by GET /repos/{repo_id}/review-performance.

    Example:
        {
          "repository_id": "9f7c2e91",
          "metrics": {"average_pr_size": 132.5,
                      "average_risk_score": 4.3,
                      "total_pull_requests": 65}
        }
    """
    repository_id: str
    metrics:       ReviewPerformanceMetrics


class ErrorResponse(BaseModel):
    """Standard error envelope for all 4xx / 5xx responses."""
    error: str