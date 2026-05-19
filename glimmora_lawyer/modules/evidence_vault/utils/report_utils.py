"""Pure helpers for assembling the final report (no I/O)."""
from __future__ import annotations

import re
from typing import Dict, List, Tuple


_CHUNK_TYPE_LABELS: Dict[str, str] = {
    "facts":              "Factual narrative",
    "procedural":         "Procedural posture",
    "witness_statement":  "Witness evidence",
    "allegation":         "Allegations & denials",
    "agreement_clause":   "Contractual basis",
    "timeline":           "Chronology",
    "court_order":        "Existing orders / judgments",
    "prayer":             "Relief sought",
    "annexure":           "Documentary exhibits",
    "evidence_reference": "Evidence references",
    "legal_argument":     "Legal grounds",
    "unidentified":       "Unclassified material",
}


def humanise_chunk_type(t: str) -> str:
    return _CHUNK_TYPE_LABELS.get(t, t.replace("_", " ").title())


_ISSUE_LEGAL_SIGNIFICANCE: Dict[str, str] = {
    "facts":              "Underpins liability and burden-shifting arguments.",
    "procedural":         "Determines maintainability, limitation, and forum choice.",
    "witness_statement":  "Provides testimonial weight; central to cross-examination.",
    "allegation":         "Defines disputed and admitted issues for framing.",
    "agreement_clause":   "Contractual breach turns on this; the operative instrument.",
    "timeline":           "Chronology controls causation and limitation arguments.",
    "court_order":        "Affects procedural posture and binding directions.",
    "prayer":             "Sets the relief envelope the bench can grant.",
    "annexure":           "Documentary corroboration of pleaded facts.",
    "evidence_reference": "Cross-reference layer linking exhibits to claims.",
    "legal_argument":     "Statutory backbone for the case theory.",
    "unidentified":       "Needs classification before reliance.",
}


def issue_legal_significance(chunk_type: str) -> str:
    return _ISSUE_LEGAL_SIGNIFICANCE.get(
        chunk_type, "Material requires further classification.",
    )


def recommended_action_for_issue(chunk_type: str, support_level: int,
                                 contradiction_impact: int,
                                 missing_impact: int) -> str:
    if missing_impact >= 50:
        return "Supplement with the missing documents flagged below."
    if contradiction_impact >= 50:
        return "Verify conflicting references before reliance in argument."
    if support_level >= 70:
        return "Lead with this — strongest leg of the case."
    if support_level <= 30:
        return "Strengthen with affidavits or supporting exhibits."
    return "Maintain; cite in chief through the most-cited chunk."


def format_score_explanation(name: str, value: int, factors_text: List[str]) -> str:
    bullets = " · ".join(t for t in factors_text if t)
    return f"{name}: {value}/100 — {bullets}" if bullets else f"{name}: {value}/100"


_CIT_RE = re.compile(r"\[[^\[\]]+\]")


def label_strip(label: str) -> str:
    return re.sub(r"\s+", " ", label or "").strip()
