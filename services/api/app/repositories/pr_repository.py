# repositories/pr_repository.py — SQL queries for pull request data

import asyncpg


async def fetch_prs_for_repo(conn, repo_owner: str, repo_name: str, limit: int, offset: int):

    rows = await conn.fetch(
        """
        SELECT
    pr.id,
    pr.pr_number,
    pr.author,
    pr.created_at,
    NULL::TIMESTAMP AS merged_at,
    pr.files_changed,
    a.lines_added,
    a.lines_removed,
    a.risk_score,
    a.risk_level
FROM pull_requests pr
LEFT JOIN pr_analysis a
    ON pr.pr_number = a.pr_number
WHERE
    pr.repo_owner = $1
    AND pr.repo_name = $2
ORDER BY pr.created_at DESC
LIMIT $3 OFFSET $4
        """,
        repo_owner,
        repo_name,
        limit,
        offset
    )

    return rows


async def count_prs_for_repo(conn, repo_owner: str, repo_name: str) -> int:

    row = await conn.fetchrow(
        """
        SELECT COUNT(*) AS count
        FROM pull_requests
        WHERE repo_owner = $1
        AND repo_name = $2
        """,
        repo_owner,
        repo_name
    )

    return row["count"] if row else 0