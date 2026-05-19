"""Weighted scoring helpers for reranking.

Keep the math interpretable: every factor is clamped to [0, 1] and the
final score is a weighted sum that can be inspected via ScoreBreakdown.
"""
from __future__ import annotations

from typing import Mapping


def clamp01(x: float) -> float:
    return max(0.0, min(1.0, float(x)))


def weighted_sum(values: Mapping[str, float], weights: Mapping[str, float]) -> float:
    """sum(weight[k] * clamp01(values[k])) — weights are not normalised here,
    so callers should choose weights that sum to ~1.0 for an interpretable
    final score in [0, 1]."""
    total = 0.0
    for k, w in weights.items():
        v = values.get(k, 0.0)
        total += w * clamp01(v)
    return total


def linear_decay(value: float, max_value: float) -> float:
    """value mapped from [0, max_value] into [0, 1], clamped."""
    if max_value <= 0:
        return 0.0
    return clamp01(value / max_value)


def recency_score(years_ago: float, half_life_years: float = 12.0) -> float:
    """Smooth decay: 1.0 if decided this year, ~0.5 at half_life, → 0.

    A precedent decided ~24y ago scores ~0.25 with the default half_life,
    which matches how lawyers usually weigh "recent" vs "older but still
    good law".
    """
    if years_ago < 0:
        return 1.0
    return clamp01(2 ** (-years_ago / max(1e-6, half_life_years)))
