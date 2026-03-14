"""
models/pr_data.py — Structured representation of a PR analysis result.

This is a plain dataclass — no ORM, no database.
Used as the single object passed between pipeline stages.
"""

from dataclasses import dataclass, field
from typing import List


@dataclass
class BreakingChange:
    """A single detected risk signal in the diff."""
    signal_type: str    # e.g. "function_signature_change", "route_deleted"
    filename:    str    # file where the signal was found


@dataclass
class PRAnalysis:
    """
    Complete analysis result for one Pull Request.

    Populated progressively as data flows through the pipeline:
      1. pr_number, author          — from GitHub PR metadata
      2. files_changed, lines_*    — from diff parser
      3. breaking_changes           — from diff parser
      4. risk_score, risk_level     — from risk scorer
    """
    pr_number:       int
    author:          str
    files_changed:   int               = 0
    lines_added:     int               = 0
    lines_removed:   int               = 0
    breaking_changes: List[BreakingChange] = field(default_factory=list)
    risk_score:      float             = 0.0
    risk_level:      str               = "LOW"