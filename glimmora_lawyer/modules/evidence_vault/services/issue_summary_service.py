"""Build the legal-issue matrix from chunks + entities.

Each unique chunk_type becomes an issue. The issue carries:
  - support_level         (0..100) — density of entities + chunk count
  - contradiction_impact  (0..100) — share of contradictions tied to its chunks
  - missing_evidence_impact (0..100) — heuristic mapping by category to issue
  - related_chunks / related_entities — for traceability
  - legal_significance    — short human rationale
  - recommended_action    — derived from the three numbers above
"""
from __future__ import annotations

from collections import defaultdict
from typing import Dict, List, Set

from loguru import logger

from modules.evidence_vault.schemas.final_report_schema import IssueSummary
from modules.evidence_vault.utils.report_utils import (
    humanise_chunk_type, issue_legal_significance, recommended_action_for_issue,
)
from modules.evidence_vault.utils.scoring_utils import (
    clamp, saturating_count,
)

log = logger.bind(scope="evidence.issues")


# Map missing-evidence categories → chunk_type buckets they impact most.
_MISSING_TO_CHUNK: Dict[str, List[str]] = {
    "Plaint / Petition":           ["allegation", "facts", "prayer"],
    "Written statement / Reply":   ["allegation", "procedural"],
    "Affidavit of evidence":       ["witness_statement", "facts"],
    "FIR / Complaint":             ["facts", "allegation"],
    "Charge sheet / s.173 report": ["procedural", "facts"],
    "Statements u/s 161 / 164":    ["witness_statement"],
    "Notice / Demand letter":      ["procedural", "allegation"],
    "Court Order / Judgment":      ["court_order", "procedural"],
    "Agreement / Contract":        ["agreement_clause", "facts"],
    "Annexures / Exhibits":        ["annexure", "evidence_reference"],
    "Correspondence (emails / letters)": ["evidence_reference", "facts"],
    "Witness statements":          ["witness_statement"],
    "Expert / Forensic report":    ["evidence_reference", "facts"],
}


def build_issue_matrix(
    *,
    chunks: List[dict],
    entities: List[dict],
    contradictions: List[dict],
    missing_items: List[dict],
) -> List[IssueSummary]:
    chunks_by_type: Dict[str, List[dict]] = defaultdict(list)
    for c in chunks:
        chunks_by_type[c.get("chunk_type", "unidentified")].append(c)

    # Map each chunk_id → chunk_type for fast lookup
    type_of_chunk: Dict[str, str] = {c.get("chunk_id"): c.get("chunk_type", "unidentified")
                                     for c in chunks}

    # Group entities by issue
    entities_by_type: Dict[str, List[str]] = defaultdict(list)
    for e in entities:
        ct = type_of_chunk.get(e.get("source_chunk_id"), "unidentified")
        entities_by_type[ct].append(e.get("entity_id", ""))

    # Group contradictions by chunk_type touched
    contradictions_by_type: Dict[str, Set[str]] = defaultdict(set)
    for ct in contradictions:
        for ref in ct.get("references") or []:
            # references look like "[file | p.X-Y | chunk N]" — we need the
            # chunk_id. We don't have it directly; approximate by matching
            # `chunk_id` field if present.
            pass
        for cid in ct.get("related_chunk_ids") or []:
            t = type_of_chunk.get(cid, "unidentified")
            contradictions_by_type[t].add(ct.get("id") or ct.get("contradiction_id") or "")

    # Missing items → chunk_type impact
    missing_by_type: Dict[str, List[dict]] = defaultdict(list)
    for m in missing_items:
        impacted_types = _MISSING_TO_CHUNK.get(m.get("category", ""), [])
        for t in impacted_types:
            missing_by_type[t].append(m)

    total_contr = max(1, len(contradictions))
    total_miss_weight = sum(
        {"low": 8, "medium": 18, "high": 30, "critical": 45}.get(m.get("severity"), 18)
        for m in missing_items
    ) or 1

    matrix: List[IssueSummary] = []
    for ct, ch_list in chunks_by_type.items():
        ent_ids = entities_by_type.get(ct, [])
        ent_count = len(ent_ids)
        support = clamp(
            saturating_count(len(ch_list), 50, 4)
            + saturating_count(ent_count, 50, 12),
        )
        contr_share = (len(contradictions_by_type.get(ct, set())) / total_contr) * 100
        contradiction_impact = clamp(contr_share)
        miss_local_w = sum(
            {"low": 8, "medium": 18, "high": 30, "critical": 45}.get(m.get("severity"), 18)
            for m in missing_by_type.get(ct, [])
        )
        missing_impact = clamp((miss_local_w / total_miss_weight) * 100)

        matrix.append(IssueSummary(
            issue_name=humanise_chunk_type(ct),
            support_level=support,
            contradiction_impact=contradiction_impact,
            missing_evidence_impact=missing_impact,
            related_entities=ent_ids[:30],
            related_chunks=[c.get("chunk_id") for c in ch_list],
            legal_significance=issue_legal_significance(ct),
            recommended_action=recommended_action_for_issue(
                ct, support, contradiction_impact, missing_impact),
        ))

    matrix.sort(key=lambda i: -i.support_level)
    log.info("Issue matrix built: {} issues", len(matrix))
    return matrix


def pick_strongest_and_weakest(matrix: List[IssueSummary]) -> tuple[str, str]:
    if not matrix:
        return "", ""
    strongest = max(matrix, key=lambda i: i.support_level).issue_name
    # weakest = lowest support BUT also penalised by missing+contradiction impact
    def _score(i):
        return i.support_level - 0.4 * i.missing_evidence_impact - 0.4 * i.contradiction_impact
    weakest = min(matrix, key=_score).issue_name
    return strongest, weakest
