"""
services/repo_service.py — Business logic for repository operations

repo_id is now a str (stable 8-char hex hash) not an int.
"""

import logging

import asyncpg
from fastapi import HTTPException

from app.repositories.repo_repository import fetch_all_repos, fetch_repo_by_id
from app.schemas.repo_schema import RepoResponse

logger = logging.getLogger(__name__)


async def get_all_repos(conn: asyncpg.Connection) -> list[RepoResponse]:
    """Return all repositories. Empty list if none exist yet."""
    rows = await fetch_all_repos(conn)
    return [
        RepoResponse(
            id             = row["id"],
            name           = row["name"],
            owner          = row["owner"],
            github_repo_id = None,
            created_at     = row["created_at"],
        )
        for row in rows
    ]


async def get_repo_by_id_or_404(
    conn:    asyncpg.Connection,
    repo_id: str,                   # str, not int
) -> asyncpg.Record:
    """
    Fetch a repository record by its stable hash ID.
    Raises HTTP 404 if the repository does not exist.
    """
    row = await fetch_repo_by_id(conn, repo_id)
    if row is None:
        logger.warning("Repository id=%s not found", repo_id)
        raise HTTPException(
            status_code = 404,
            detail      = {"error": f"Repository '{repo_id}' not found"},
        )
    return row