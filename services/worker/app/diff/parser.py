"""
diff/parser.py — Analyze GitHub file objects for risk signals.

Input:
    A list of file dicts as returned by the GitHub Files API.
    Each dict has: filename, additions, deletions, patch (optional).

Output:
    files_changed     int
    lines_added       int
    lines_removed     int
    breaking_changes  list[BreakingChange]  — deduplicated

Safety rule:
    patch may be absent (binary files, oversized diffs, GitHub truncation).
    The parser NEVER crashes due to a missing patch — it simply skips
    patch analysis for that file while still counting additions/deletions.

Deduplication:
    A (signal_type, filename) pair is only added once even if multiple
    detectors fire for the same file.
"""

import re
import logging
from typing import List

from app.models.pr_data import BreakingChange

logger = logging.getLogger(__name__)

# ── Config file name patterns ─────────────────────────────────────────────────
CONFIG_PATTERNS: tuple[str, ...] = (
    ".env",
    "config",
    "settings",
    ".yaml",
    ".yml",
    ".json",
)

# ── Patch-level regex patterns ────────────────────────────────────────────────

# Removed function definition line (Python / JS / TS)
_RE_FUNC_REMOVED = re.compile(
    r'^-.*\bdef\s+\w+\s*\(|^-.*\bfunction\s+\w+\s*\(',
    re.MULTILINE,
)

# Added function definition line
_RE_FUNC_ADDED = re.compile(
    r'^\+.*\bdef\s+\w+\s*\(|^\+.*\bfunction\s+\w+\s*\(',
    re.MULTILINE,
)

# Removed route decorator or route registration
_RE_ROUTE_REMOVED = re.compile(
    r'^-.*@app\.route\s*\(|'
    r'^-.*@router\.\w+\s*\(|'
    r'^-.*app\.(get|post|put|delete|patch)\s*\(',
    re.MULTILINE | re.IGNORECASE,
)

# Threshold for "large file change" signal
LARGE_CHANGE_THRESHOLD = 200


# ── Helpers ───────────────────────────────────────────────────────────────────

def _is_config_file(filename: str) -> bool:
    lower = filename.lower()
    return any(pattern in lower for pattern in CONFIG_PATTERNS)


def _detect_patch_signals(filename: str, patch: str) -> List[BreakingChange]:
    """
    Analyze one file's patch text for function-signature and route signals.
    Only called when patch is a non-empty string.
    """
    signals: List[BreakingChange] = []

    # Function signature change: removed def AND added def in same patch
    if _RE_FUNC_REMOVED.search(patch) and _RE_FUNC_ADDED.search(patch):
        signals.append(BreakingChange(
            signal_type = "function_signature_change",
            filename    = filename,
        ))

    # Route deleted: removed route decorator
    if _RE_ROUTE_REMOVED.search(patch):
        signals.append(BreakingChange(
            signal_type = "route_deleted",
            filename    = filename,
        ))

    return signals


def _deduplicate(changes: List[BreakingChange]) -> List[BreakingChange]:
    """
    Remove duplicate (signal_type, filename) pairs.

    A duplicate can arise when the same file matches more than one
    detection pass (e.g. a large config file triggers both
    config_file_change and large_file_change — those are distinct
    signal_types and are kept). Only exact duplicates are removed.
    """
    seen:   set[tuple[str, str]] = set()
    unique: List[BreakingChange] = []
    for bc in changes:
        key = (bc.signal_type, bc.filename)
        if key not in seen:
            seen.add(key)
            unique.append(bc)
    return unique


# ── Public API ────────────────────────────────────────────────────────────────

def parse_diff(files: list[dict]) -> dict:
    """
    Analyze a list of GitHub file objects and return risk signals.

    Args:
        files: Raw list from GitHub /pulls/{number}/files endpoint.

    Returns:
        {
            "files_changed":    int,
            "lines_added":      int,
            "lines_removed":    int,
            "breaking_changes": List[BreakingChange],   # deduplicated
        }
    """
    lines_added:      int                  = 0
    lines_removed:    int                  = 0
    breaking_changes: List[BreakingChange] = []

    for file_obj in files:
        filename  = file_obj.get("filename", "")
        additions = file_obj.get("additions", 0)
        deletions = file_obj.get("deletions", 0)
        patch     = file_obj.get("patch")       # may be None

        lines_added   += additions
        lines_removed += deletions

        # Config file — detected from filename alone, no patch required
        if _is_config_file(filename):
            breaking_changes.append(BreakingChange(
                signal_type = "config_file_change",
                filename    = filename,
            ))
            logger.debug("config_file_change: %s", filename)

        # Large change — detected from counters alone, no patch required
        if additions > LARGE_CHANGE_THRESHOLD or deletions > LARGE_CHANGE_THRESHOLD:
            breaking_changes.append(BreakingChange(
                signal_type = "large_file_change",
                filename    = filename,
            ))
            logger.debug("large_file_change: %s (%d+/%d-)", filename, additions, deletions)

        # Patch-level signals — only when patch text is present
        if patch is None:
            logger.debug("No patch for %s — skipping patch analysis", filename)
            continue

        breaking_changes.extend(_detect_patch_signals(filename, patch))

    # Deduplicate before returning
    unique_changes = _deduplicate(breaking_changes)

    return {
        "files_changed":    len(files),
        "lines_added":      lines_added,
        "lines_removed":    lines_removed,
        "breaking_changes": unique_changes,
    }