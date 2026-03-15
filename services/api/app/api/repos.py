"""
api/repos.py — Repository and pull request routes

GET /repos                    — list all repositories
GET /repos/{repo_id}/prs     — list PRs for a repository (paginated)

repo_id is now a str (stable 8-char hex hash).
"""

import logging
from typing import Annotated

import asyncpg
from fastapi import APIRouter, Depends, Query

from app.config import PAGINATION_DEFAULT_LIMIT, PAGINATION_MAX_LIMIT
from app.db.database import get_db
from app.repositories.pr_repository import fetch_prs_for_repo, count_prs_for_repo
from app.schemas.pr_schema import PRResponse, PRListResponse
from app.schemas.repo_schema import RepoResponse
from app.services.repo_service import get_all_repos, get_repo_by_id_or_404

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get(
    "/repos",
    response_model = list[RepoResponse],
    summary        = "List all repositories",
)
async def list_repos(
    conn: asyncpg.Connection = Depends(get_db),
) -> list[RepoResponse]:
    """Return all repositories tracked by PRPulse."""
    return await get_all_repos(conn)


@router.get(
    "/repos/{repo_id}/prs",
    response_model = PRListResponse,
    summary        = "List pull requests for a repository",
    responses      = {404: {"description": "Repository not found"}},
)
async def list_prs(
    repo_id: str,                                                         # str, not int
    limit:   Annotated[int, Query(ge=1, le=PAGINATION_MAX_LIMIT)] = PAGINATION_DEFAULT_LIMIT,
    offset:  Annotated[int, Query(ge=0)]                          = 0,
    conn:    asyncpg.Connection                                    = Depends(get_db),
) -> PRListResponse:
    """
    Return paginated pull requests for the given repository.

    - **limit**: records to return (1–200, default 50)
    - **offset**: records to skip (default 0)
    """
    repo  = await get_repo_by_id_or_404(conn, repo_id)
    rows  = await fetch_prs_for_repo(
        conn       = conn,
        repo_owner = repo["owner"],
        repo_name  = repo["name"],
        limit      = limit,
        offset     = offset,
    )
    total = await count_prs_for_repo(
        conn       = conn,
        repo_owner = repo["owner"],
        repo_name  = repo["name"],
    )

    items = [
        PRResponse(
            id            = row["id"],
            pr_number     = row["pr_number"],
            author        = row["author"],
            created_at    = row["created_at"],
            merged_at     = row["merged_at"],
            lines_added   = row["lines_added"],
            lines_removed = row["lines_removed"],
            files_changed = row["files_changed"],
            risk_score    = row["risk_score"],
            risk_level    = row["risk_level"],
        )
        for row in rows
    ]

    return PRListResponse(items=items, total=total, limit=limit, offset=offset)