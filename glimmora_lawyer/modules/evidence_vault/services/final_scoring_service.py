"""Deterministic scoring for the Final Analysis Dashboard.

All formulas are transparent and recorded as ScoreBreakdown.factors so the
UI can show *why* each score landed where it did. Inputs come from the
already-built artifacts (canonical, chunks, entities, partitions,
contradictions, missing-evidence). No LLM calls live here.
"""
from __future__ import annotations

from typing import Dict, List

from loguru import logger

from modules.evidence_vault.schemas.scoring_schema import (
    ScoreBreakdown, ScoreFactor, ScoreSet,
)
from modules.evidence_vault.utils.scoring_utils import (
    clamp, safe_avg, saturating_count, severity_weight,
)

log = logger.bind(scope="evidence.scoring")


# ---------- Inputs ----------

def _doc_count(canonicals: List[dict]) -> int:
    return len(canonicals)


def _chunk_density(canonicals: List[dict]) -> int:
    return sum(len(c.get("chunks") or []) for c in canonicals)


def _entity_avg_confidence(entities: List[dict]) -> float:
    return safe_avg([float(e.get("confidence") or 0.0) for e in entities])


def _partition_population(partitions: List[dict]) -> int:
    """How many of the 5 partitions actually carry entities."""
    return sum(1 for p in partitions if len(p.get("entities") or []) > 0)


def _legal_basis_count(partitions: List[dict]) -> int:
    for p in partitions:
        if p.get("partition_type") == "legal_basis":
            return len(p.get("entities") or [])
    return 0


def _timeline_entities(partitions: List[dict]) -> List[dict]:
    for p in partitions:
        if p.get("partition_type") == "timeline":
            return p.get("entities") or []
    return []


def _is_iso_date(s: str) -> bool:
    return bool(s) and len(s) == 10 and s[4] == "-" and s[7] == "-"


# ---------- Individual scores ----------

def _evidence_strength(canonicals: List[dict], entities: List[dict],
                       partitions: List[dict]) -> ScoreBreakdown:
    docs = _doc_count(canonicals)
    chunks = _chunk_density(canonicals)
    ent_conf = _entity_avg_confidence(entities)
    partitions_filled = _partition_population(partitions)

    f1 = saturating_count(docs, 25, 6)            # +25 by 6 docs
    f2 = saturating_count(chunks, 20, 30)         # +20 by 30 chunks
    f3 = saturating_count(len(entities), 20, 60)  # +20 by 60 entities
    f4 = (partitions_filled / 5) * 25             # +25 by full coverage
    f5 = ent_conf * 10                            # +10 by perfect confidence

    raw = f1 + f2 + f3 + f4 + f5
    value = clamp(raw)
    factors = [
        ScoreFactor(name="documents",  contribution=round(f1, 1),
                    explanation=f"{docs} document(s) attached"),
        ScoreFactor(name="chunk_density", contribution=round(f2, 1),
                    explanation=f"{chunks} chunk(s) across the case"),
        ScoreFactor(name="entity_volume", contribution=round(f3, 1),
                    explanation=f"{len(entities)} entity rows lifted"),
        ScoreFactor(name="partition_coverage", contribution=round(f4, 1),
                    explanation=f"{partitions_filled}/5 partitions populated"),
        ScoreFactor(name="entity_confidence", contribution=round(f5, 1),
                    explanation=f"avg entity confidence = {ent_conf:.2f}"),
    ]
    return ScoreBreakdown(
        score_name="evidence_strength_score",
        value=value, direction="higher_better",
        explanation=(f"{docs} docs · {chunks} chunks · {len(entities)} entities · "
                     f"{partitions_filled}/5 partitions · conf {ent_conf:.2f}"),
        factors=factors,
    )


def _evidence_weakness(strength_value: int, contradictions: List[dict],
                       missing_items: List[dict],
                       entities: List[dict]) -> ScoreBreakdown:
    base = max(0, 60 - int(0.6 * strength_value))  # base inverse of strength
    contr_w = sum(severity_weight(c.get("severity")) for c in contradictions)
    miss_w = sum(severity_weight(m.get("severity")) for m in missing_items)
    low_conf_count = sum(1 for e in entities if float(e.get("confidence") or 0) < 0.55)
    low_w = min(15, low_conf_count)

    raw = base + min(30, contr_w * 0.7) + min(30, miss_w * 0.5) + low_w
    value = clamp(raw)
    factors = [
        ScoreFactor(name="inverse_strength", contribution=base,
                    explanation=f"floor of 60 − 60% of strength ({strength_value})"),
        ScoreFactor(name="contradictions",
                    contribution=round(min(30, contr_w * 0.7), 1),
                    explanation=f"{len(contradictions)} contradiction(s), severity-weighted"),
        ScoreFactor(name="missing_evidence",
                    contribution=round(min(30, miss_w * 0.5), 1),
                    explanation=f"{len(missing_items)} missing item(s), severity-weighted"),
        ScoreFactor(name="low_confidence_entities", contribution=low_w,
                    explanation=f"{low_conf_count} entity(ies) below 0.55 confidence"),
    ]
    return ScoreBreakdown(
        score_name="evidence_weakness_score",
        value=value, direction="lower_better",
        explanation=("inverse strength penalised by contradictions, missing "
                     "evidence, and low-confidence entities"),
        factors=factors,
    )


def _completeness(partitions: List[dict],
                  missing_items: List[dict]) -> ScoreBreakdown:
    filled = _partition_population(partitions)
    base = (filled / 5) * 100
    miss_w = sum(severity_weight(m.get("severity")) for m in missing_items)
    penalty = min(40, miss_w * 0.4)
    value = clamp(base - penalty)
    return ScoreBreakdown(
        score_name="completeness_score", value=value, direction="higher_better",
        explanation=(f"{filled}/5 partitions populated, minus penalty for "
                     f"{len(missing_items)} missing item(s)"),
        factors=[
            ScoreFactor(name="partitions_filled", contribution=round(base, 1),
                        explanation=f"{filled} of 5 partitions populated"),
            ScoreFactor(name="missing_penalty", contribution=-round(penalty, 1),
                        explanation=f"-min(40, severity·0.4) over {len(missing_items)} item(s)"),
        ],
    )


def _contradiction_risk(contradictions: List[dict]) -> ScoreBreakdown:
    high = sum(1 for c in contradictions if c.get("severity") == "high")
    crit = sum(1 for c in contradictions if c.get("severity") == "critical")
    med = sum(1 for c in contradictions if c.get("severity") == "medium")
    low = sum(1 for c in contradictions if c.get("severity") == "low")
    raw = crit * 35 + high * 22 + med * 12 + low * 5
    value = clamp(raw)
    return ScoreBreakdown(
        score_name="contradiction_risk_score", value=value, direction="lower_better",
        explanation=(f"{crit} critical, {high} high, {med} medium, {low} low "
                     f"severity contradictions"),
        factors=[
            ScoreFactor(name="critical", contribution=crit * 35,
                        explanation=f"{crit} critical contradiction(s)"),
            ScoreFactor(name="high",     contribution=high * 22,
                        explanation=f"{high} high-severity contradiction(s)"),
            ScoreFactor(name="medium",   contribution=med * 12,
                        explanation=f"{med} medium-severity contradiction(s)"),
            ScoreFactor(name="low",      contribution=low * 5,
                        explanation=f"{low} low-severity contradiction(s)"),
        ],
    )


def _missing_risk(missing_items: List[dict]) -> ScoreBreakdown:
    total_w = sum(severity_weight(m.get("severity")) for m in missing_items)
    value = clamp(total_w)
    severities = [m.get("severity", "medium") for m in missing_items]
    return ScoreBreakdown(
        score_name="missing_evidence_risk_score",
        value=value, direction="lower_better",
        explanation=(f"{len(missing_items)} missing item(s) — severity mix: "
                     f"{', '.join(severities) or 'none'}"),
        factors=[
            ScoreFactor(name="severity_sum", contribution=total_w,
                        explanation=f"sum of severity weights = {total_w}"),
        ],
    )


def _timeline_integrity(partitions: List[dict],
                        contradictions: List[dict]) -> ScoreBreakdown:
    timeline = _timeline_entities(partitions)
    dates = [e for e in timeline if e.get("entity_type") == "DATE"]
    events = [e for e in timeline if e.get("entity_type") == "EVENT"]
    iso_dates = [e for e in dates if _is_iso_date(e.get("normalized_value", ""))]

    f1 = saturating_count(len(dates), 35, 8)
    f2 = saturating_count(len(events), 25, 8)
    f3 = (len(iso_dates) / len(dates)) * 25 if dates else 0
    date_contr = sum(1 for c in contradictions if c.get("kind") == "date")
    penalty = min(35, date_contr * 18)
    value = clamp(f1 + f2 + f3 - penalty)
    return ScoreBreakdown(
        score_name="timeline_integrity_score",
        value=value, direction="higher_better",
        explanation=(f"{len(dates)} date(s) ({len(iso_dates)} normalised) · "
                     f"{len(events)} event(s) · {date_contr} date conflict(s)"),
        factors=[
            ScoreFactor(name="dates",  contribution=round(f1, 1),
                        explanation=f"{len(dates)} date entity(ies)"),
            ScoreFactor(name="events", contribution=round(f2, 1),
                        explanation=f"{len(events)} event entity(ies)"),
            ScoreFactor(name="iso_normalisation", contribution=round(f3, 1),
                        explanation=f"{len(iso_dates)}/{len(dates) or 1} dates ISO-normalised"),
            ScoreFactor(name="date_contradictions_penalty", contribution=-penalty,
                        explanation=f"-min(35, {date_contr}·18)"),
        ],
    )


def _legal_basis_strength(partitions: List[dict]) -> ScoreBreakdown:
    cnt = _legal_basis_count(partitions)
    distinct_sections = set()
    distinct_acts = set()
    distinct_clauses = set()
    for p in partitions:
        if p.get("partition_type") != "legal_basis":
            continue
        for e in p.get("entities") or []:
            et = e.get("entity_type")
            v = e.get("normalized_value") or e.get("value") or ""
            if et == "SECTION":
                distinct_sections.add(v)
            elif et in ("ACT", "LAW"):
                distinct_acts.add(v)
            elif et == "CLAUSE":
                distinct_clauses.add(v)

    f1 = saturating_count(cnt, 40, 10)
    f2 = saturating_count(len(distinct_sections), 25, 6)
    f3 = saturating_count(len(distinct_acts),     20, 3)
    f4 = saturating_count(len(distinct_clauses),  15, 4)
    value = clamp(f1 + f2 + f3 + f4)
    return ScoreBreakdown(
        score_name="legal_basis_strength_score",
        value=value, direction="higher_better",
        explanation=(f"{cnt} legal_basis entity(ies); distinct: "
                     f"{len(distinct_sections)} sections, "
                     f"{len(distinct_acts)} acts, "
                     f"{len(distinct_clauses)} clauses"),
        factors=[
            ScoreFactor(name="volume", contribution=round(f1, 1),
                        explanation=f"{cnt} legal_basis entities"),
            ScoreFactor(name="distinct_sections", contribution=round(f2, 1),
                        explanation=f"{len(distinct_sections)} distinct sections"),
            ScoreFactor(name="distinct_acts", contribution=round(f3, 1),
                        explanation=f"{len(distinct_acts)} distinct acts"),
            ScoreFactor(name="distinct_clauses", contribution=round(f4, 1),
                        explanation=f"{len(distinct_clauses)} distinct clauses"),
        ],
    )


def compute_seven_input_scores(
    *,
    canonicals: List[dict],
    chunks: List[dict],
    entities: List[dict],
    partitions: List[dict],
    contradictions: List[dict],
    missing_items: List[dict],
) -> List[ScoreBreakdown]:
    """Returns the 7 'input' scores (strength, weakness, completeness, contr,
    missing, timeline, legal_basis). Readiness + pitch are derived in
    readiness_service from these."""
    strength = _evidence_strength(canonicals, entities, partitions)
    weakness = _evidence_weakness(strength.value, contradictions,
                                  missing_items, entities)
    completeness = _completeness(partitions, missing_items)
    contradiction_risk = _contradiction_risk(contradictions)
    missing_risk = _missing_risk(missing_items)
    timeline_integrity = _timeline_integrity(partitions, contradictions)
    legal_basis = _legal_basis_strength(partitions)

    log.info("Scores: strength={} weakness={} completeness={} contr_risk={} "
             "missing_risk={} timeline={} legal_basis={}",
             strength.value, weakness.value, completeness.value,
             contradiction_risk.value, missing_risk.value,
             timeline_integrity.value, legal_basis.value)

    return [strength, weakness, completeness, contradiction_risk,
            missing_risk, timeline_integrity, legal_basis]


def assemble_score_set(breakdowns: List[ScoreBreakdown]) -> ScoreSet:
    by_name: Dict[str, int] = {b.score_name: b.value for b in breakdowns}
    return ScoreSet(**{k: by_name.get(k, 0) for k in ScoreSet.model_fields.keys()})
