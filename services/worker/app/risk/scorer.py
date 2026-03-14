"""
risk/scorer.py — Deterministic rule-based PR risk scoring.

Input:
    files_changed   int
    lines_added     int
    lines_removed   int
    breaking_changes  list[BreakingChange]

Scoring rules:
    files_changed > 10              → +15
    lines_added   > 300             → +20
    lines_removed > 200             → +10
    any breaking change detected    → +40
    any config file change          → +15

Score ranges:
    LOW     0  – 30
    MEDIUM  31 – 60
    HIGH    61 – 100

Output:
    { "risk_score": float, "risk_level": "LOW" | "MEDIUM" | "HIGH" }
"""

import logging
from typing import List

from app.models.pr_data import BreakingChange

logger = logging.getLogger(__name__)


def compute_risk(
    files_changed:    int,
    lines_added:      int,
    lines_removed:    int,
    breaking_changes: List[BreakingChange],
) -> dict:
    """
    Compute a deterministic risk score from PR analysis signals.

    Each rule contributes a fixed number of points.
    The final score is clamped to [0, 100].

    Returns:
        {"risk_score": float, "risk_level": str}
    """
    score: float = 0.0

    # Rule 1: many files changed
    if files_changed > 10:
        score += 15
        logger.debug("Rule: files_changed > 10 (+15)")

    # Rule 2: large addition
    if lines_added > 300:
        score += 20
        logger.debug("Rule: lines_added > 300 (+20)")

    # Rule 3: large deletion
    if lines_removed > 200:
        score += 10
        logger.debug("Rule: lines_removed > 200 (+10)")

    # Rule 4: any breaking change signal detected
    has_breaking = len(breaking_changes) > 0
    if has_breaking:
        score += 40
        logger.debug("Rule: breaking_changes detected (+40)")

    # Rule 5: config file changed (may already be captured as breaking change,
    #          but scores independently as a distinct risk dimension)
    has_config_change = any(
        bc.signal_type == "config_file_change" for bc in breaking_changes
    )
    if has_config_change:
        score += 15
        logger.debug("Rule: config_file_change detected (+15)")

    # Clamp to valid range
    score = max(0.0, min(100.0, score))

    # Classify
    if score <= 30:
        risk_level = "LOW"
    elif score <= 60:
        risk_level = "MEDIUM"
    else:
        risk_level = "HIGH"

    logger.debug("Final risk: score=%.1f level=%s", score, risk_level)

    return {
        "risk_score": score,
        "risk_level": risk_level,
    }