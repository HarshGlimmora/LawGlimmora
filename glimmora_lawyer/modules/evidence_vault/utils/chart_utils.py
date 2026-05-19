"""Tiny chart-data builders. Render-side uses Streamlit's built-in chart API.

Keeping the data shaping outside the page makes this unit-testable.
"""
from __future__ import annotations

from typing import Dict, List


_SCORE_LABELS: Dict[str, str] = {
    "evidence_strength_score":     "Evidence strength",
    "evidence_weakness_score":     "Evidence weakness",
    "completeness_score":          "Completeness",
    "contradiction_risk_score":    "Contradiction risk",
    "missing_evidence_risk_score": "Missing-evidence risk",
    "timeline_integrity_score":    "Timeline integrity",
    "legal_basis_strength_score":  "Legal-basis strength",
    "readiness_score":             "Hearing readiness",
    "pitch_success_estimate":      "Pitch success",
}


_SCORE_DIRECTION: Dict[str, bool] = {
    # True = higher better
    "evidence_strength_score":     True,
    "evidence_weakness_score":     False,
    "completeness_score":          True,
    "contradiction_risk_score":    False,
    "missing_evidence_risk_score": False,
    "timeline_integrity_score":    True,
    "legal_basis_strength_score":  True,
    "readiness_score":             True,
    "pitch_success_estimate":      True,
}


def score_label(key: str) -> str:
    return _SCORE_LABELS.get(key, key)


def is_higher_better(key: str) -> bool:
    return _SCORE_DIRECTION.get(key, True)


def scores_for_bar_chart(scores: dict) -> Dict[str, int]:
    """Returns {human_label: value} ordered for a horizontal bar chart.

    We intentionally invert lower-better scores so the chart reads as
    "higher is better across the board"."""
    out: Dict[str, int] = {}
    for key, label in _SCORE_LABELS.items():
        value = int(scores.get(key, 0))
        if not _SCORE_DIRECTION[key]:
            value = 100 - value
            label = f"{label} (inverted)"
        out[label] = value
    return out


def issue_matrix_for_bar_chart(issues: List[dict]) -> Dict[str, int]:
    return {iss["issue_name"]: int(iss.get("support_level", 0))
            for iss in issues}
