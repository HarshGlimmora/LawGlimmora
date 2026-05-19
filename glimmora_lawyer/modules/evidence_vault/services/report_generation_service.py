"""Final-report orchestrator.

Runs the 14-step processing flow specified for Phase 5:
  1. Load canonical evidence JSON
  2. Load chunks
  3. Load entities
  4. Load partitions
  5. Load contradictions          (computed in-place if absent)
  6. Load missing evidence        (computed in-place if absent)
  7. Load retrieval/chat history if relevant
  8. Generate issue summaries
  9. Compute all scores
 10. Generate recommendations
 11. Generate final report object
 12. Save final report outputs
 13. (UI renders)
 14. (Export options served from saved files)

Contradiction and missing-evidence detection were excluded from earlier
phases. To keep this layer self-contained, lightweight deterministic
detectors live here as private helpers (`_detect_contradictions`,
`_detect_missing`). Their outputs persist to `reports/contradictions.json`
and `reports/missing_evidence.json` so the retrieval + chat layers can also
pick them up.
"""
from __future__ import annotations

import json
import re
import uuid
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from loguru import logger

from config.settings import SETTINGS
from modules.case.services.case_service import get_case
from modules.evidence_vault.schemas.final_report_schema import (
    ContradictionSummary, EvidencePoint, FinalReport,
    MissingEvidenceSummary, SourceMapEntry,
)
from modules.evidence_vault.schemas.recommendation_schema import (
    Recommendation, RecommendationPlan,
)
from modules.evidence_vault.schemas.scoring_schema import (
    ScoreBreakdown, ScoreSummary,
)
from modules.evidence_vault.services.ai_extractor import (
    gemini_model, get_gemini_client,
)
from modules.evidence_vault.services.chunk_persistence_service import (
    load_case_chunks, load_case_entities, load_case_partitions,
)
from modules.evidence_vault.services.final_scoring_service import (
    assemble_score_set, compute_seven_input_scores,
)
from modules.evidence_vault.services.issue_summary_service import (
    build_issue_matrix, pick_strongest_and_weakest,
)
from modules.evidence_vault.services.persistence_service import (
    case_evidence_root, ensure_case_dirs, iter_documents_for_case_or_none,
)
from modules.evidence_vault.services.readiness_service import (
    compute_pitch_success, compute_readiness,
)
from modules.evidence_vault.services.recommendation_service import (
    build_recommendations,
)
from modules.evidence_vault.utils.scoring_utils import severity_weight

log = logger.bind(scope="evidence.report")


# ---------- File paths ----------

def reports_root(case_id: int | str) -> Path:
    return case_evidence_root(case_id) / "reports"


def _ensure() -> None:
    pass


# ---------- Deterministic contradiction + missing detectors ----------

_MONEY_NOUNS = ("damages", "consideration", "fee", "penalty", "interest",
                "compensation", "salary", "deposit", "advance")


def _money_norm(raw: str) -> str:
    return "".join(ch for ch in (raw or "") if ch.isalnum() or ch == ".").lower()


def _detect_contradictions(chunks: List[dict],
                           entities: List[dict]) -> List[dict]:
    """Three rule sets:
      * party_role  — same person/org in opposing roles
      * amount      — same money-noun, different totals
      * date        — same event-verb dated differently across chunks
    """
    out: List[dict] = []
    chunk_by_id = {c.get("chunk_id"): c for c in chunks}

    def _anchor_label(chunk_id: str) -> Optional[str]:
        c = chunk_by_id.get(chunk_id)
        if not c:
            return None
        return (c.get("citation_anchor") or {}).get("citation_label")

    # --- Party-role flip ---
    party_roles = {"plaintiff", "defendant", "petitioner", "respondent",
                   "appellant", "complainant", "accused", "claimant"}
    # Each chunk records which roles appear in it
    roles_by_chunk: Dict[str, set] = defaultdict(set)
    names_by_chunk: Dict[str, set] = defaultdict(set)
    for e in entities:
        if e.get("entity_type") not in ("PERSON", "ORG", "WITNESS"):
            continue
        cid = e.get("source_chunk_id")
        val = (e.get("value") or "").strip()
        if val.lower() in party_roles:
            roles_by_chunk[cid].add(val.lower())
        else:
            names_by_chunk[cid].add(val)

    # Pair name across chunks → roles seen alongside it
    name_to_roles: Dict[str, set] = defaultdict(set)
    name_to_chunks: Dict[str, set] = defaultdict(set)
    for cid, names in names_by_chunk.items():
        roles = roles_by_chunk.get(cid, set())
        for name in names:
            for r in roles:
                name_to_roles[name].add(r)
                name_to_chunks[name].add(cid)

    opposing = [
        {"plaintiff", "defendant"}, {"petitioner", "respondent"},
        {"appellant", "respondent"}, {"complainant", "accused"},
    ]
    for name, roles in name_to_roles.items():
        if any(pair.issubset(roles) for pair in opposing):
            refs = [(_anchor_label(c) or c) for c in list(name_to_chunks[name])[:6]]
            out.append({
                "id": "contr-" + uuid.uuid4().hex[:8],
                "kind": "party_role", "severity": "high",
                "summary": f"{name} appears in opposing roles within this case",
                "explanation": (f"{name} is associated with roles "
                                f"{sorted(roles)} across the evidence."),
                "references": [r for r in refs if isinstance(r, str)],
                "related_chunk_ids": list(name_to_chunks[name]),
            })

    # --- Amount conflicts ---
    money_by_noun: Dict[str, Dict[str, List[str]]] = defaultdict(
        lambda: defaultdict(list))
    for c in chunks:
        text = (c.get("clean_text") or "").lower()
        for noun in _MONEY_NOUNS:
            if noun in text:
                for e in entities:
                    if (e.get("entity_type") == "AMOUNT"
                            and e.get("source_chunk_id") == c.get("chunk_id")):
                        money_by_noun[noun][_money_norm(e.get("value"))].append(
                            c.get("chunk_id"))
    for noun, by_amount in money_by_noun.items():
        if len(by_amount) >= 2:
            chunk_ids = []
            for v in by_amount.values():
                chunk_ids.extend(v[:2])
            refs = [(_anchor_label(c) or c) for c in chunk_ids[:6]]
            out.append({
                "id": "contr-" + uuid.uuid4().hex[:8],
                "kind": "amount", "severity": "medium",
                "summary": f"Conflicting figures attached to '{noun}'",
                "explanation": (f"At least {len(by_amount)} distinct amounts "
                                f"are associated with '{noun}' across the evidence."),
                "references": [r for r in refs if isinstance(r, str)],
                "related_chunk_ids": list(set(chunk_ids)),
            })

    # --- Date conflicts on same event-verb across chunks ---
    verb_chunks: Dict[str, set] = defaultdict(set)
    date_in_chunk: Dict[str, List[str]] = defaultdict(list)
    for e in entities:
        if e.get("entity_type") == "EVENT":
            verb_chunks[(e.get("value") or "").lower()].add(e.get("source_chunk_id"))
        elif e.get("entity_type") == "DATE":
            iso = (e.get("normalized_value") or "").strip()
            if iso:
                date_in_chunk[e.get("source_chunk_id")].append(iso)
    for verb, cids in verb_chunks.items():
        dates_seen: Dict[str, set] = defaultdict(set)
        for cid in cids:
            for d in date_in_chunk.get(cid, []):
                dates_seen[d].add(cid)
        if len(dates_seen) >= 2:
            chunk_ids = []
            for v in dates_seen.values():
                chunk_ids.extend(list(v)[:2])
            refs = [(_anchor_label(c) or c) for c in chunk_ids[:6]]
            out.append({
                "id": "contr-" + uuid.uuid4().hex[:8],
                "kind": "date", "severity": "medium",
                "summary": f"Action '{verb}' is dated differently across chunks",
                "explanation": (f"'{verb}' is associated with {len(dates_seen)} "
                                f"distinct ISO dates ({', '.join(sorted(dates_seen.keys())[:4])})."),
                "references": [r for r in refs if isinstance(r, str)],
                "related_chunk_ids": list(set(chunk_ids)),
            })

    log.info("Contradiction detection: {} flagged", len(out))
    return out


_CASE_TYPE_EXPECTATIONS: Dict[str, List[str]] = {
    "Civil suit": [
        "Plaint / Petition", "Written statement / Reply", "Affidavit of evidence",
        "Court Order / Judgment", "Annexures / Exhibits",
        "Correspondence (emails / letters)",
    ],
    "Writ petition": [
        "Plaint / Petition", "Affidavit of evidence", "Court Order / Judgment",
        "Notice / Demand letter", "Annexures / Exhibits",
    ],
    "Criminal complaint": [
        "FIR / Complaint", "Charge sheet / s.173 report", "Statements u/s 161 / 164",
        "Witness statements", "Expert / Forensic report", "Court Order / Judgment",
    ],
    "Arbitration": [
        "Agreement / Contract", "Notice / Demand letter",
        "Affidavit of evidence", "Annexures / Exhibits",
    ],
    "Commercial dispute": [
        "Agreement / Contract", "Notice / Demand letter",
        "Correspondence (emails / letters)", "Annexures / Exhibits",
        "Court Order / Judgment",
    ],
    "Family matter": [
        "Plaint / Petition", "Affidavit of evidence",
        "Notice / Demand letter", "Annexures / Exhibits",
    ],
    "Tax appeal": [
        "Notice / Demand letter", "Court Order / Judgment",
        "Annexures / Exhibits", "Expert / Forensic report",
    ],
    "Consumer complaint": [
        "FIR / Complaint", "Notice / Demand letter",
        "Annexures / Exhibits", "Correspondence (emails / letters)",
    ],
    "Service matter": [
        "Plaint / Petition", "Notice / Demand letter",
        "Court Order / Judgment", "Annexures / Exhibits",
    ],
    "Insolvency": [
        "Agreement / Contract", "Notice / Demand letter",
        "Annexures / Exhibits", "Affidavit of evidence",
    ],
    "Other": [],
}

_CATEGORY_MATCHERS: Dict[str, tuple] = {
    "Plaint / Petition":                ("petition", "pleading", "plaint"),
    "Written statement / Reply":        ("pleading", "reply"),
    "Affidavit of evidence":            ("affidavit",),
    "FIR / Complaint":                  ("fir", "complaint"),
    "Charge sheet / s.173 report":      ("charge sheet",),
    "Statements u/s 161 / 164":         ("statement",),
    "Notice / Demand letter":           ("notice", "legal notice"),
    "Court Order / Judgment":           ("order", "judgment"),
    "Agreement / Contract":             ("agreement", "contract"),
    "Annexures / Exhibits":             ("annexure", "exhibit"),
    "Correspondence (emails / letters)": ("correspondence", "email", "letter"),
    "Witness statements":               ("witness",),
    "Expert / Forensic report":         ("expert", "forensic", "report"),
}

_RATIONALE: Dict[str, str] = {
    "Plaint / Petition":      "Foundational pleading defines the cause of action and prayer.",
    "Written statement / Reply": "Without the opposing pleading, contested issues cannot be framed.",
    "Affidavit of evidence":  "Affidavit forms the testimonial backbone in chief.",
    "FIR / Complaint":        "Initiating document fixing the date, place, and allegation.",
    "Charge sheet / s.173 report": "Police conclusions and charges shape the trial scope.",
    "Statements u/s 161 / 164": "Witness statements anchor cross-examination strategy.",
    "Notice / Demand letter": "Pre-litigation notice establishes knowledge and limitation.",
    "Court Order / Judgment": "Interim orders and prior rulings frame the procedural posture.",
    "Agreement / Contract":   "The underlying instrument is the central exhibit in contract matters.",
    "Annexures / Exhibits":   "Documentary exhibits substantiate pleaded facts.",
    "Correspondence (emails / letters)": "Correspondence often supplies admissions, dates, and intent.",
    "Witness statements":     "Statements ground the human-evidence side of the case.",
    "Expert / Forensic report": "Expert opinion is often dispositive on technical or medical facts.",
}


def _detect_missing(user_id: int, case_id: int,
                    canonicals: List[dict]) -> List[dict]:
    case = get_case(user_id, case_id)
    case_type = (case or {}).get("case_type") or "Other"
    expected = list(_CASE_TYPE_EXPECTATIONS.get(case_type, []))
    universal = {"Annexures / Exhibits", "Correspondence (emails / letters)"}
    for u in universal:
        if u not in expected:
            expected.append(u)

    present: set = set()
    for d in canonicals:
        evt = ((d.get("document") or {}).get("doc_type") or "").lower()
        for cat, needles in _CATEGORY_MATCHERS.items():
            if any(n in evt for n in needles):
                present.add(cat)

    gaps = [c for c in expected if c not in present]
    items: List[dict] = []
    for cat in gaps:
        severity = "high" if cat in (
            "Plaint / Petition", "Agreement / Contract", "FIR / Complaint",
            "Charge sheet / s.173 report",
        ) else "medium"
        items.append({
            "id": "miss-" + uuid.uuid4().hex[:8],
            "category": cat,
            "severity": severity,
            "why_it_matters": _RATIONALE.get(cat, "Recommended for completeness."),
            "recommendation": f"Upload the {cat.lower()} to close this evidence gap.",
        })
    log.info("Missing-evidence detection: case_type={} expected={} present={} gaps={}",
             case_type, len(expected), len(present), len(items))
    return items


def _persist_index(case_id: int | str, name: str, items: List[dict]) -> Path:
    ensure_case_dirs(case_id)
    p = reports_root(case_id) / f"{name}.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps({"items": items}, indent=2, default=str),
                 encoding="utf-8")
    return p


# ---------- Strongest / weakest evidence points ----------

def _evidence_points(canonicals: List[dict], entities: List[dict]) -> tuple[List[EvidencePoint], List[EvidencePoint]]:
    """Density = entity_count_in_chunk + 3 * claim_count_in_chunk."""
    entity_counts: Dict[str, int] = Counter()
    for e in entities:
        entity_counts[e.get("source_chunk_id", "")] += 1

    all_points: List[EvidencePoint] = []
    for d in canonicals:
        doc_meta = d.get("document") or {}
        for ch in d.get("chunks") or []:
            cid = ch.get("chunk_id")
            density = entity_counts.get(cid, 0)
            anchor = ch.get("citation_anchor") or {}
            all_points.append(EvidencePoint(
                title=(ch.get("chunk_type") or "chunk")[:80],
                snippet=(ch.get("clean_text") or "")[:280],
                citation_label=anchor.get("citation_label", "") or "",
                chunk_id=cid or "",
                document_id=ch.get("document_id") or doc_meta.get("document_id", ""),
                page=int(anchor.get("page_start") or 1),
                score=float(density),
            ))
    if not all_points:
        return [], []
    all_points.sort(key=lambda p: -p.score)
    strongest = all_points[:5]
    weakest = sorted(all_points, key=lambda p: (p.score, len(p.snippet)))[:5]
    return strongest, weakest


# ---------- Narrative (Gemini, with deterministic fallback) ----------

_NARRATIVE_SCHEMA: dict = {
    "type": "OBJECT",
    "properties": {
        "executive_summary": {"type": "STRING"},
        "final_conclusion":  {"type": "STRING"},
    },
    "required": ["executive_summary", "final_conclusion"],
}


def _narrative_prompt(*, case_label: str, scores: dict,
                      strongest_issue: str, weakest_issue: str,
                      contradictions: List[dict],
                      missing_items: List[dict]) -> str:
    return f"""You are Glimmora Lawyer's senior counsel-grade report writer.
Compose two short, sober paragraphs for a final case-intelligence report
from the deterministic signals below. Do not invent facts. Do not cite
specific page numbers — those live elsewhere in the report.

Case label: {case_label}

Scorecard (0-100):
{json.dumps(scores, indent=2)}

Strongest issue: {strongest_issue or '—'}
Weakest issue:   {weakest_issue or '—'}

Contradictions ({len(contradictions)}):
{json.dumps([{'kind': c.get('kind'), 'severity': c.get('severity'), 'summary': c.get('summary')} for c in contradictions[:5]], indent=2)}

Missing evidence ({len(missing_items)}):
{json.dumps([{'category': m.get('category'), 'severity': m.get('severity')} for m in missing_items[:8]], indent=2)}

Return JSON with two fields:
  - executive_summary  (3-5 sentences, factual, neutral tone)
  - final_conclusion   (2-3 sentences, what counsel should do next)"""


def _generate_narrative(*, case_label: str, scores: dict,
                        strongest_issue: str, weakest_issue: str,
                        contradictions: List[dict],
                        missing_items: List[dict]) -> tuple[str, str, str]:
    """Returns (executive_summary, final_conclusion, source_label)."""
    client, kind = get_gemini_client()
    if client is None:
        return _fallback_narrative(scores, strongest_issue, weakest_issue,
                                   contradictions, missing_items)
    from google.genai import types  # type: ignore

    prompt = _narrative_prompt(
        case_label=case_label, scores=scores,
        strongest_issue=strongest_issue, weakest_issue=weakest_issue,
        contradictions=contradictions, missing_items=missing_items,
    )
    try:
        resp = client.models.generate_content(
            model=gemini_model("final_report"),
            contents=[prompt],
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=_NARRATIVE_SCHEMA,
                temperature=0.15,
            ),
        )
        raw = (getattr(resp, "text", "") or "").strip()
        data = json.loads(raw)
        exec_summary = (data.get("executive_summary") or "").strip()
        conclusion = (data.get("final_conclusion") or "").strip()
        if not exec_summary or not conclusion:
            raise ValueError("empty narrative fields")
        log.info("Narrative via {}: summary_len={} conclusion_len={}",
                 kind, len(exec_summary), len(conclusion))
        return exec_summary, conclusion, kind or "vertex"
    except Exception as exc:
        log.error("Gemini narrative failed ({}). Using fallback.", exc)
        return _fallback_narrative(scores, strongest_issue, weakest_issue,
                                   contradictions, missing_items)


def _fallback_narrative(scores: dict, strongest_issue: str, weakest_issue: str,
                        contradictions: List[dict],
                        missing_items: List[dict]) -> tuple[str, str, str]:
    readiness = scores.get("readiness_score", 0)
    strength = scores.get("evidence_strength_score", 0)
    completeness = scores.get("completeness_score", 0)
    contr_risk = scores.get("contradiction_risk_score", 0)
    miss_risk = scores.get("missing_evidence_risk_score", 0)
    posture = ("ready" if readiness >= 65
               else "broadly serviceable" if readiness >= 40
               else "not yet ready")

    exec_summary = (
        f"On the present evidence record the case is {posture} for hearing "
        f"(readiness {readiness}/100; evidence strength {strength}/100; "
        f"completeness {completeness}/100). "
        f"The strongest leg is {strongest_issue or '—'}; the most exposed leg "
        f"is {weakest_issue or '—'}. "
        f"{len(contradictions)} contradiction(s) and {len(missing_items)} "
        f"evidence gap(s) have been flagged for resolution."
    )
    conclusion = (
        f"Counsel should prioritise closing the {len(missing_items)} "
        f"evidence gap(s) and reconciling the {len(contradictions)} flagged "
        f"contradiction(s) before relying on this record at hearing. "
        f"Contradiction risk currently scores {contr_risk}/100 and missing-"
        f"evidence risk {miss_risk}/100 — both are reduced by the recommended "
        f"next actions listed below."
    )
    return exec_summary, conclusion, "fallback"


# ---------- Source map ----------

def _build_source_map(canonicals: List[dict],
                      strongest_points: List[EvidencePoint],
                      weakest_points: List[EvidencePoint],
                      contradictions: List[dict],
                      missing_items: List[dict]) -> List[SourceMapEntry]:
    out: List[SourceMapEntry] = []
    seen: set = set()
    def _push(label: str, doc_id: str, chunk_id: str, page: int, reason: str) -> None:
        if not label or label in seen:
            return
        seen.add(label)
        out.append(SourceMapEntry(
            label=label, document_id=doc_id, chunk_id=chunk_id,
            page_number=page, reason_used=reason,
        ))

    for p in strongest_points:
        _push(p.citation_label, p.document_id, p.chunk_id, p.page,
              "Cited as strongest-evidence point in the scorecard.")
    for p in weakest_points:
        _push(p.citation_label, p.document_id, p.chunk_id, p.page,
              "Cited as risky / weak evidence point in the scorecard.")
    for c in contradictions:
        for ref in (c.get("references") or [])[:4]:
            if isinstance(ref, str) and ref.startswith("["):
                _push(ref, "", "", 1,
                      f"Cited in contradiction ({c.get('kind')}, {c.get('severity')}).")
    return out


# ---------- Public entry ----------

def generate_final_report(*, user_id: int, case_id: int) -> FinalReport:
    """End-to-end orchestrator. Persists every output file."""
    ensure_case_dirs(case_id)

    # 1. canonicals (per doc)
    canonicals: List[dict] = []
    for d in iter_documents_for_case_or_none(case_id):
        if d:
            canonicals.append(d)
    log.info("Loaded {} canonical document(s)", len(canonicals))

    # 2-4. chunks/entities/partitions (case-level aggregates)
    chunks_payload = load_case_chunks(case_id) or {}
    entities_payload = load_case_entities(case_id) or {}
    partitions_payload = load_case_partitions(case_id) or {}
    chunks = chunks_payload.get("chunks") or []
    entities = entities_payload.get("entities") or []
    partitions = partitions_payload.get("partitions") or []

    # 5. contradictions
    contradictions_path = reports_root(case_id) / "contradictions.json"
    if contradictions_path.exists():
        try:
            contradictions = json.loads(contradictions_path.read_text(encoding="utf-8")).get("items", [])
        except Exception:
            contradictions = []
    else:
        contradictions = _detect_contradictions(chunks, entities)
        _persist_index(case_id, "contradictions", contradictions)

    # 6. missing evidence
    missing_path = reports_root(case_id) / "missing_evidence.json"
    if missing_path.exists():
        try:
            missing_items = json.loads(missing_path.read_text(encoding="utf-8")).get("items", [])
        except Exception:
            missing_items = []
    else:
        missing_items = _detect_missing(user_id, case_id, canonicals)
        _persist_index(case_id, "missing_evidence", missing_items)

    # 8. Issue matrix
    issue_matrix = build_issue_matrix(
        chunks=chunks, entities=entities,
        contradictions=contradictions, missing_items=missing_items,
    )
    strongest_issue, weakest_issue = pick_strongest_and_weakest(issue_matrix)

    # 9. Scores
    input_breakdowns = compute_seven_input_scores(
        canonicals=canonicals, chunks=chunks, entities=entities,
        partitions=partitions, contradictions=contradictions,
        missing_items=missing_items,
    )
    readiness = compute_readiness(input_breakdowns)
    pitch = compute_pitch_success(input_breakdowns)
    breakdowns: List[ScoreBreakdown] = input_breakdowns + [readiness, pitch]
    score_set = assemble_score_set(breakdowns)

    # 10. Recommendations
    recs: List[Recommendation] = build_recommendations(
        missing_items=missing_items, contradictions=contradictions,
        issue_matrix=issue_matrix,
    )

    # Strongest / weakest evidence points
    strongest_points, weakest_points = _evidence_points(canonicals, entities)

    # Contradiction + missing summaries
    contradiction_summaries = [
        ContradictionSummary(
            contradiction_id=c.get("id") or "",
            kind=c.get("kind", "—"),
            severity=c.get("severity", "medium"),
            summary=c.get("summary", ""),
            explanation=c.get("explanation", ""),
            references=[r for r in (c.get("references") or []) if isinstance(r, str)],
        ) for c in contradictions
    ]
    missing_summaries = [
        MissingEvidenceSummary(
            missing_id=m.get("id") or "",
            category=m.get("category", ""),
            severity=m.get("severity", "medium"),
            why_it_matters=m.get("why_it_matters", ""),
            recommendation=m.get("recommendation", ""),
        ) for m in missing_items
    ]

    # Source map
    source_map = _build_source_map(
        canonicals, strongest_points, weakest_points,
        contradictions, missing_items,
    )

    # Narrative
    case_meta = get_case(user_id, case_id) or {}
    case_label = case_meta.get("case_name") or f"Case {case_id}"
    exec_summary, final_conclusion, narrative_source = _generate_narrative(
        case_label=case_label,
        scores=score_set.model_dump(),
        strongest_issue=strongest_issue, weakest_issue=weakest_issue,
        contradictions=contradictions, missing_items=missing_items,
    )

    report = FinalReport(
        report_id="rpt-" + uuid.uuid4().hex[:12],
        case_id=str(case_id),
        generated_at=datetime.utcnow(),
        scores=score_set,
        executive_summary=exec_summary,
        strongest_issue=strongest_issue,
        weakest_issue=weakest_issue,
        strongest_points=strongest_points,
        weakest_points=weakest_points,
        contradiction_summary=contradiction_summaries,
        missing_evidence_summary=missing_summaries,
        issue_matrix=issue_matrix,
        recommendations=recs,
        final_conclusion=final_conclusion,
        source_map=source_map,
        narrative_source=narrative_source,  # type: ignore[arg-type]
    )

    # 12. Persist all outputs
    _persist_final_report(case_id, report, breakdowns, recs)
    log.info(
        "Final report saved for case={} readiness={} pitch={} narrative={}",
        case_id, score_set.readiness_score,
        score_set.pitch_success_estimate, narrative_source,
    )
    return report


def _persist_final_report(case_id: int | str, report: FinalReport,
                          breakdowns: List[ScoreBreakdown],
                          recommendations: List[Recommendation]) -> None:
    ensure_case_dirs(case_id)
    root = reports_root(case_id)
    root.mkdir(parents=True, exist_ok=True)

    (root / "final_report.json").write_text(
        report.model_dump_json(indent=2), encoding="utf-8")

    summary = ScoreSummary(
        case_id=str(case_id), generated_at=report.generated_at,
        scores=report.scores, breakdowns=breakdowns,
    )
    (root / "score_summary.json").write_text(
        summary.model_dump_json(indent=2), encoding="utf-8")

    plan = RecommendationPlan(case_id=str(case_id), items=recommendations)
    (root / "recommendation_plan.json").write_text(
        plan.model_dump_json(indent=2), encoding="utf-8")

    # UI cache — lightweight payload the dashboard re-renders from.
    cache: Dict[str, Any] = {
        "case_id": str(case_id),
        "report_id": report.report_id,
        "generated_at": report.generated_at.isoformat(timespec="seconds"),
        "scores": report.scores.model_dump(),
        "strongest_issue": report.strongest_issue,
        "weakest_issue": report.weakest_issue,
        "counts": {
            "documents": len({p.document_id for p in report.strongest_points}),
            "issues": len(report.issue_matrix),
            "contradictions": len(report.contradiction_summary),
            "missing": len(report.missing_evidence_summary),
            "recommendations": len(report.recommendations),
            "source_map_entries": len(report.source_map),
        },
        "narrative_source": report.narrative_source,
    }
    (root / "final_dashboard_cache.json").write_text(
        json.dumps(cache, indent=2, default=str), encoding="utf-8")


def load_final_report(case_id: int | str) -> Optional[FinalReport]:
    p = reports_root(case_id) / "final_report.json"
    if not p.exists():
        return None
    return FinalReport.model_validate_json(p.read_text(encoding="utf-8"))


def load_dashboard_cache(case_id: int | str) -> Optional[dict]:
    p = reports_root(case_id) / "final_dashboard_cache.json"
    if not p.exists():
        return None
    return json.loads(p.read_text(encoding="utf-8"))


def load_score_summary(case_id: int | str) -> Optional[ScoreSummary]:
    p = reports_root(case_id) / "score_summary.json"
    if not p.exists():
        return None
    return ScoreSummary.model_validate_json(p.read_text(encoding="utf-8"))
