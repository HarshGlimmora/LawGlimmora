"""Indian court hierarchy + binding-level helpers.

Used by reranking to translate raw `court` strings into a comparable rank
(0..1) and to decide whether a precedent is binding/persuasive for the
querying case.

The ranks are deliberately coarse — we are surfacing relative authority,
not adjudicating it. A precedent's *actual* binding effect depends on the
forum hearing the matter, which the lawyer interprets in context.
"""
from __future__ import annotations

import re
from typing import Tuple


# Coarse-grained tiers. Higher = more authoritative.
_RANKS: dict[str, float] = {
    "supreme_court":     1.00,
    "constitutional":    0.95,   # constitution bench / 5-judge bench cues
    "high_court":        0.78,
    "tribunal_national": 0.62,   # NCLAT, ITAT (national), SAT
    "tribunal_state":    0.50,   # NCLT, state tax tribunals
    "district":          0.35,
    "commission":        0.30,
    "unknown":           0.10,
}


_PATTERNS: list[tuple[re.Pattern, str]] = [
    (re.compile(r"\bsupreme\s+court\b", re.I),                  "supreme_court"),
    (re.compile(r"\bconstitution\s+bench\b", re.I),             "constitutional"),
    (re.compile(r"\bhigh\s+court\b", re.I),                     "high_court"),
    (re.compile(r"\b(?:NCLAT|National Company Law Appellate"
                r"|Securities Appellate|SAT|TDSAT|Armed Forces"
                r"\s+Appellate|ITAT|Income Tax Appellate)\b", re.I),
                                                                "tribunal_national"),
    (re.compile(r"\b(?:NCLT|Debts Recovery|DRT|State Consumer"
                r"|Tax Tribunal)\b", re.I),                     "tribunal_state"),
    (re.compile(r"\b(?:District|Sessions|Magistrate|Civil Judge)"
                r"\b", re.I),                                   "district"),
    (re.compile(r"\b(?:Commission|Ombudsman|Authority)\b", re.I),
                                                                "commission"),
]


def classify_court(court_label: str) -> Tuple[str, float]:
    """Returns ("supreme_court", 1.00) etc. Unknown → ("unknown", 0.10)."""
    if not court_label:
        return "unknown", _RANKS["unknown"]
    for pat, key in _PATTERNS:
        if pat.search(court_label):
            return key, _RANKS[key]
    return "unknown", _RANKS["unknown"]


def court_rank(court_label: str) -> float:
    return classify_court(court_label)[1]


def infer_binding_level(
    precedent_court: str,
    forum_jurisdiction: str | None = None,
) -> str:
    """Rough binding-level inference.

    - Supreme Court → binding everywhere.
    - High Court → binding within its jurisdiction (we can't tell which
      jurisdiction from a free-text label, so we mark "persuasive" by
      default and let the lawyer adjust).
    - Tribunals → persuasive.
    - Anything else → informational.
    """
    key, _ = classify_court(precedent_court)
    if key == "supreme_court" or key == "constitutional":
        return "binding"
    if key == "high_court":
        return "persuasive"
    if key in ("tribunal_national", "tribunal_state"):
        return "persuasive"
    return "informational"
