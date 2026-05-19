"""Generic, side-effect-free helpers shared by the scoring services."""
from __future__ import annotations

from typing import Dict, List


def clamp(value: float, lo: float = 0, hi: float = 100) -> int:
    """Clamp + round to int. Used everywhere a 0..100 score is emitted."""
    return int(max(lo, min(hi, round(value))))


_SEVERITY_WEIGHTS: Dict[str, int] = {
    "low": 8, "medium": 18, "high": 30, "critical": 45,
}


def severity_weight(severity: str) -> int:
    return _SEVERITY_WEIGHTS.get((severity or "").lower(), _SEVERITY_WEIGHTS["medium"])


def saturating_count(n: int, cap: int, full_at: int) -> float:
    """Map a count to 0..cap; reaches `cap` at `full_at` observations.
    Used to give diminishing returns to "more docs / more entities"."""
    if full_at <= 0:
        return cap
    return min(cap, (n / full_at) * cap)


def directional_tone(value: int, *, higher_better: bool = True) -> str:
    """Return a UI tone keyword ('success', 'warning', 'danger') based on
    the score's direction. The page CSS already maps these to colours."""
    if higher_better:
        return "success" if value >= 65 else "warning" if value >= 40 else "danger"
    return "success" if value <= 30 else "warning" if value <= 60 else "danger"


def safe_avg(values: List[float], default: float = 0.0) -> float:
    return sum(values) / len(values) if values else default
