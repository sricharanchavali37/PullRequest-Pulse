"""
github/client.py — Async GitHub API client

Responsibilities:
  - Fetch PR metadata      GET /repos/{owner}/{repo}/pulls/{number}
  - Fetch PR changed files GET /repos/{owner}/{repo}/pulls/{number}/files
    with full pagination (GitHub returns max 100 files per page)

Design:
  - A single httpx.AsyncClient is created once and reused for the
    lifetime of the worker process (passed in at construction time).
    This avoids the overhead of creating a new TCP connection per request
    and is the correct pattern for a long-running async service.

  - The module also exposes a module-level client instance and
    convenience functions so worker.py can call without managing state.

All requests:
  - Authorization: Bearer <GITHUB_TOKEN>
  - Accept: application/vnd.github+json
  - Timeout: 10 seconds
  - Retry up to 3 times on network errors or HTTP 5xx (exponential backoff)
  - Warn when X-RateLimit-Remaining < 100
"""

import asyncio
import logging

import httpx

from app.config import (
    GITHUB_TOKEN,
    GITHUB_API_BASE,
    GITHUB_API_TIMEOUT,
    GITHUB_MAX_RETRIES,
)

logger = logging.getLogger(__name__)

RATE_LIMIT_WARN_THRESHOLD = 100

# ── Shared client instance ────────────────────────────────────────────────────
# Created once at module import time and reused across all requests.
# A single AsyncClient maintains a connection pool, which avoids
# reconnecting to GitHub's servers on every API call.
_client: httpx.AsyncClient = httpx.AsyncClient(
    timeout = httpx.Timeout(GITHUB_API_TIMEOUT),
    headers = {
        "Authorization":     f"Bearer {GITHUB_TOKEN}",
        "Accept":            "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    },
)


async def close_client() -> None:
    """
    Gracefully close the shared HTTP client.
    Call this on worker shutdown to release open connections.
    """
    await _client.aclose()


# ── Internal helpers ──────────────────────────────────────────────────────────

def _check_rate_limit(response: httpx.Response) -> None:
    """Warn when the GitHub API rate limit budget is running low."""
    remaining = response.headers.get("X-RateLimit-Remaining")
    reset_at  = response.headers.get("X-RateLimit-Reset")
    if remaining is not None:
        try:
            if int(remaining) < RATE_LIMIT_WARN_THRESHOLD:
                logger.warning(
                    "GitHub rate limit low: %s requests remaining "
                    "(resets at Unix timestamp %s)",
                    remaining, reset_at,
                )
        except ValueError:
            pass


async def _get_with_retry(url: str, params: dict | None = None) -> dict | list:
    """
    GET request using the shared client, with exponential-backoff retry.

    Retry on:
      - httpx.TransportError  (network errors, connection reset)
      - HTTP 5xx              (transient server errors)

    Raise immediately on:
      - HTTP 4xx              (caller error — retrying won't help)
      - Exhausted retry budget

    Backoff: 1s → 2s → 4s  (2^(attempt-1))
    """
    last_exc: Exception | None = None

    for attempt in range(1, GITHUB_MAX_RETRIES + 1):
        try:
            response = await _client.get(url, params=params or {})

            _check_rate_limit(response)

            if response.status_code >= 500:
                logger.warning(
                    "GitHub API %s for %s (attempt %d/%d)",
                    response.status_code, url, attempt, GITHUB_MAX_RETRIES,
                )
                last_exc = httpx.HTTPStatusError(
                    f"HTTP {response.status_code}",
                    request  = response.request,
                    response = response,
                )
                await asyncio.sleep(2 ** (attempt - 1))
                continue

            # 4xx — raise immediately, no retry
            response.raise_for_status()
            return response.json()

        except httpx.TransportError as exc:
            logger.warning(
                "Network error on attempt %d/%d for %s: %s",
                attempt, GITHUB_MAX_RETRIES, url, exc,
            )
            last_exc = exc
            await asyncio.sleep(2 ** (attempt - 1))

    raise RuntimeError(
        f"GitHub API request failed after {GITHUB_MAX_RETRIES} attempts "
        f"({url}): {last_exc}"
    )


# ── Public API ────────────────────────────────────────────────────────────────

async def fetch_pr_metadata(owner: str, repo: str, pr_number: int) -> dict:
    """
    Fetch full Pull Request metadata.
    Returns the GitHub PR object as a plain dict.
    """
    url = f"{GITHUB_API_BASE}/repos/{owner}/{repo}/pulls/{pr_number}"
    logger.debug("Fetching PR metadata: %s", url)
    result = await _get_with_retry(url)
    return result  # type: ignore[return-value]


async def fetch_pr_files(owner: str, repo: str, pr_number: int) -> list[dict]:
    """
    Fetch all files changed in a Pull Request.

    Follows GitHub's pagination: requests page=1, page=2, ... until
    an empty page is returned or a page has fewer than 100 items.

    Returns a single flat list of all file objects across all pages.
    Each item contains: filename, additions, deletions, patch (optional).
    """
    all_files: list[dict] = []
    page = 1

    while True:
        url    = f"{GITHUB_API_BASE}/repos/{owner}/{repo}/pulls/{pr_number}/files"
        params = {"per_page": 100, "page": page}

        logger.debug("Fetching PR #%d files — page %d", pr_number, page)
        page_data = await _get_with_retry(url, params=params)

        if not page_data:           # empty page → no more files
            break

        all_files.extend(page_data)

        if len(page_data) < 100:    # partial page → last page
            break

        page += 1

    logger.debug("PR #%d — total files fetched: %d", pr_number, len(all_files))
    return all_files