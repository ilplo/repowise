"""Shared hotspot classification policy."""

from __future__ import annotations

HOTSPOT_PERCENTILE_THRESHOLD: float = 0.75
HOTSPOT_MIN_COMMITS_90D: int = 5


def is_hotspot(
    *,
    churn_percentile: float,
    commit_count_90d: int,
) -> bool:
    """Return whether a file has enough relative and absolute churn to be hot."""
    return (
        churn_percentile >= HOTSPOT_PERCENTILE_THRESHOLD
        and commit_count_90d >= HOTSPOT_MIN_COMMITS_90D
    )
