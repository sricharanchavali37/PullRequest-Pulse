"""
repositories/repo_repository.py — SQL queries for repository data

No dedicated repositories table exists.  Repository identity is derived
from distinct (repo_owner, repo_name) pairs in pull_requests.

Stable ID strategy:
  The old ROW_NUMBER() approach produced IDs that changed when new
  repositories appeared.  We now use PostgreSQL's md5() function:

      id = LEFT(md5(repo_owner || '/' || repo_name), 8)

  This produces a deterministic 8-character hex string from the
  owner/name pair.  The same owner/name always produces the same ID,
  regardless of how many other repositories exist.

  Example: md5('acme/prpulse') → '9f7c2e91...' → id = '9f7c2e91'
"""

import logging

import asyncpg

logger = logging.getLogger(__name__)


async def fetch_all_repos(conn: asyncpg.Connection) -> list[asyncpg.Record]:
    """
    Return all distinct repositories derived from pull_requests.

    Columns returned:
      id          — stable 8-char hex derived from md5(owner/name)
      name        — repo_name
      owner       — repo_owner
      created_at  — earliest PR created_at for this repo
    """
    rows = await conn.fetch(
        """
        SELECT
            LEFT(MD5(repo_owner || '/' || repo_name), 8) AS id,
            repo_name                                     AS name,
            repo_owner                                    AS owner,
            MIN(created_at)                               AS created_at
        FROM pull_requests
        WHERE
            repo_owner IS NOT NULL
            AND repo_name IS NOT NULL
        GROUP BY repo_owner, repo_name
        ORDER BY repo_owner, repo_name
        """
    )
    logger.debug("fetch_all_repos → %d repos", len(rows))
    return rows


async def fetch_repo_by_id(
    conn:    asyncpg.Connection,
    repo_id: str,
) -> asyncpg.Record | None:
    """
    Return a single repository by its stable hash ID.

    Scans distinct (repo_owner, repo_name) pairs, computes the hash
    for each, and returns the matching row.  Because the hash is
    deterministic, this result is stable across all requests.
    """
    row = await conn.fetchrow(
        """
        SELECT
            LEFT(MD5(repo_owner || '/' || repo_name), 8) AS id,
            repo_name                                     AS name,
            repo_owner                                    AS owner,
            MIN(created_at)                               AS created_at
        FROM pull_requests
        WHERE
            repo_owner IS NOT NULL
            AND repo_name IS NOT NULL
        GROUP BY repo_owner, repo_name
        HAVING LEFT(MD5(repo_owner || '/' || repo_name), 8) = $1
        """,
        repo_id,
    )
    return row