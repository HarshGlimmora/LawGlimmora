"""Composite scores: readiness_score and pitch_success_estimate."""
from __future__ import annotations

from typing import Dict, List

from loguru import logger

from modules.evidence_vault.schemas.scoring_schema import (
    ScoreBreakdown, ScoreFactor,
)
from modules.evidence_vault.utils.scoring_utils import clamp

log = logger.bind(scope="evidence.readiness")


def _by_name(breakdowns: List[ScoreBreakdown]) -> Dict[str, ScoreBreakdown]:
    return {b.score_name: b for b in breakdowns}


def compute_readiness(input_breakdowns: List[ScoreBreakdown]) -> ScoreBreakdown:
    """Weighted composite. Higher = more ready for hearing / brief."""
    b = _by_name(input_breakdowns)
    s    = b["evidence_strength_score"].value
    c    = b["completeness_score"].value
    cr   = b["contradiction_risk_score"].value
    mr   = b["missing_evidence_risk_score"].value
    ti   = b["timeline_integrity_score"].value
    lb   = b["legal_basis_strength_score"].value

    raw = (0.25 * s) + (0.20 * c) + (0.10 * ti) + (0.10 * lb) \
          - (0.15 * cr) - (0.20 * mr)
    # Re-anchor to a 0..100 view: best-case raw is ~65, worst is ~ -35, so map.
    value = clamp(raw + 35)

    factors = [
        ScoreFactor(name="evidence_strength",  contribution=0.25 * s,
                    explanation=f"+0.25 × {s}"),
        ScoreFactor(name="completeness",        contribution=0.20 * c,
                    explanation=f"+0.20 × {c}"),
        ScoreFactor(name="timeline_integrity",  contribution=0.10 * ti,
                    explanation=f"+0.10 × {ti}"),
        ScoreFactor(name="legal_basis",         contribution=0.10 * lb,
                    explanation=f"+0.10 × {lb}"),
        ScoreFactor(name="contradiction_risk",  contribution=-0.15 * cr,
                    explanation=f"-0.15 × {cr}"),
        ScoreFactor(name="missing_evidence_risk", contribution=-0.20 * mr,
                    explanation=f"-0.20 × {mr}"),
    ]
    log.info("Readiness composite={} (raw={})", value, round(raw, 2))
    return ScoreBreakdown(
        score_name="readiness_score", value=value, direction="higher_better",
        explanation=("weighted composite of strength, completeness, timeline, "
                     "legal-basis, minus contradiction + missing risk"),
        factors=factors,
    )


def compute_pitch_success(input_breakdowns: List[ScoreBreakdown]) -> ScoreBreakdown:
    """Pitch success — how confidently the lawyer can sell this case to a client
    or partner. Leans more on strength + legal basis, less on procedural posture.
    """
    b = _by_name(input_breakdowns)
    s   = b["evidence_strength_score"].value
    w   = b["evidence_weakness_score"].value
    c   = b["completeness_score"].value
    lb  = b["legal_basis_strength_score"].value

    raw = (0.40 * s) + (0.20 * c) + (0.20 * lb) - (0.20 * w)
    value = clamp(raw + 20)
    log.info("Pitch success composite={} (raw={})", value, round(raw, 2))
    return ScoreBreakdown(
        score_name="pitch_success_estimate", value=value, direction="higher_better",
        explanation=("weighted composite of strength + legal-basis + "
                     "completeness, penalised by weakness"),
        factors=[
            ScoreFactor(name="evidence_strength", contribution=0.40 * s,
                        explanation=f"+0.40 × {s}"),
            ScoreFactor(name="completeness",      contribution=0.20 * c,
                        explanation=f"+0.20 × {c}"),
            ScoreFactor(name="legal_basis",       contribution=0.20 * lb,
                        explanation=f"+0.20 × {lb}"),
            ScoreFactor(name="evidence_weakness", contribution=-0.20 * w,
                        explanation=f"-0.20 × {w}"),
        ],
    )
