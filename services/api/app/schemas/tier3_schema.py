"""
schemas/tier3_schema.py — Pydantic response models for Tier-3 endpoints

Three new response types:
  CycleTimeResponse       — GET /repos/{id}/cycle-time
  ReviewerLeaderboard     — GET /repos/{id}/reviewers
  WeeklyTrendResponse     — GET /repos/{id}/trends
"""

from pydantic import BaseModel


# ── Cycle time ────────────────────────────────────────────────────────────────

class CycleTimeMetrics(BaseModel):
    """
    How long PRs take from open to merge.

    avg_hours:    mean cycle time across merged PRs
    median_hours: 50th percentile — less skewed by outliers than average
    min_hours:    fastest merge
    max_hours:    slowest merge
    sample_size:  how many merged PRs this is computed over
    period_days:  how many days back the query looks (default 30)

    All values are None when no merged PRs exist yet.
    """
    repository_id: str
    avg_hours:     float | None = None
    median_hours:  float | None = None
    min_hours:     float | None = None
    max_hours:     float | None = None
    sample_size:   int          = 0
    period_days:   int          = 30


class CycleTimeResponse(BaseModel):
    repository_id: str
    cycle_time:    CycleTimeMetrics


# ── Reviewer leaderboard ──────────────────────────────────────────────────────

class ReviewerStats(BaseModel):
    """
    Per-reviewer stats for the leaderboard.

    reviewer:             GitHub login
    total_reviews:        number of reviews submitted
    avg_response_hours:   average hours from PR open to review
    approvals:            count of 'approved' reviews
    change_requests:      count of 'changes_requested' reviews
    comments:             count of 'commented' reviews
    approval_rate_pct:    approvals / total_reviews * 100
    """
    reviewer:           str
    total_reviews:      int
    avg_response_hours: float = 0.0
    approvals:          int   = 0
    change_requests:    int   = 0
    comments:           int   = 0
    approval_rate_pct:  float = 0.0


class ReviewerLeaderboardResponse(BaseModel):
    """
    Returned by GET /repos/{id}/reviewers.
    Reviewers sorted by total_reviews descending.
    """
    repository_id: str
    period_days:   int
    reviewers:     list[ReviewerStats]


# ── Weekly trends ─────────────────────────────────────────────────────────────

class WeeklySnapshot(BaseModel):
    """
    One week of aggregated metrics.
    week_start is the Monday that begins the week (ISO date string).
    """
    week_start:               str
    prs_opened:               int   = 0
    prs_merged:               int   = 0
    avg_risk_score:           float = 0.0
    avg_cycle_time_hours:     float = 0.0
    avg_review_latency_hours: float = 0.0
    avg_pr_size:              float = 0.0
    high_risk_count:          int   = 0


class WeeklyTrendResponse(BaseModel):
    """
    Returned by GET /repos/{id}/trends.
    Weeks are ordered oldest → newest so a chart can plot them left → right.
    """
    repository_id: str
    weeks:         list[WeeklySnapshot]
