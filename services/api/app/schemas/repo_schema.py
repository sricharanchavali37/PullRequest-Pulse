"""
schemas/repo_schema.py — Pydantic response models for repositories

Repository IDs are now stable 8-character hex strings derived from
md5(owner + '/' + name).  The id field type changes from int to str.
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class RepoResponse(BaseModel):
    """
    A repository as returned by GET /repos.

    id         — stable 8-char hex: LEFT(md5(owner/name), 8)
    name       — repo_name from pull_requests
    owner      — repo_owner from pull_requests
    created_at — earliest PR created_at for this owner/name pair
    """
    id:             str                    # was int; now stable hash string
    name:           str
    owner:          str
    github_repo_id: Optional[int]      = None
    created_at:     Optional[datetime] = None

    model_config = {"from_attributes": True}