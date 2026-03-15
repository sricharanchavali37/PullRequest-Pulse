"""
schemas/pr_schema.py — Pydantic response models for pull requests

These models define exactly what the API returns to clients.
They are separate from the database layer so the API contract can
evolve independently of the schema.
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class PRResponse(BaseModel):
    """
    A single pull request as returned by GET /repos/{repo_id}/prs.

    Fields map to columns in pull_requests joined with pr_analysis.
    """
    id:            int
    pr_number:     int
    author:        Optional[str]       = None
    created_at:    Optional[datetime]  = None
    merged_at:     Optional[datetime]  = None   # not in current schema; None until added
    lines_added:   Optional[int]       = None
    lines_removed: Optional[int]       = None
    files_changed: Optional[int]       = None
    risk_score:    Optional[float]     = None
    risk_level:    Optional[str]       = None

    model_config = {"from_attributes": True}


class PRListResponse(BaseModel):
    """Paginated list of pull requests."""
    items:  list[PRResponse]
    total:  int
    limit:  int
    offset: int