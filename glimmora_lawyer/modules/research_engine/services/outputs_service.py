"""Build the DownstreamPayload consumed by Packages 3, 4, 5.

The aggregation is intentionally conservative:

  * top_authorities: dedupe by document_id across sessions, keep the
    instance with the highest similarity_score. Cap at 10.
  * timeline_items: extract dated mentions from each precedent's metadata
    (date_decided) and headnote (best-effort regex). The lawyer can later
    add fact-pattern dates from Package 1 / Package 3.
  * case_strength_signals: normalised 0..1 metrics derived from the
    corpus + sessions — how much binding support exists, how recent the
    sources are, how well the corpus covers issue tags.
  * unresolved_legal_issues: issue tags that appear in any document's
    metadata but never showed up in a session's grounded authorities.

This payload is persisted to outputs/downstream.json and is the only thing
downstream packages should import.
"""
from __future__ import annotations

import re
from datetime import date, datetime
from typing import Dict, List

from loguru import logger

from modules.research_engine.schemas.answer_schema import SupportingAuthority
from modules.research_engine.schemas.outputs_schema import (
    DownstreamPayload, TimelineItem,
)
from modules.research_engine.services.indexing_service import (
    load_metadata_index,
)
from modules.research_engine.services.persistence_service import (
    downstream_path, ensure_case_dirs,
)
from modules.research_engine.services.session_service import list_sessions
from modules.research_engine.utils.score_utils import clamp01


log = logger.bind(scope="research.outputs")


_DATE_RE = re.compile(
    r"\b(?:on\s+|dated\s+)?"
    r"(?P<day>\d{1,2})\s+"
    r"(?P<mon>Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)[a-z]*\.?\s+"
    r"(?P<year>\d{4})\b",
    re.I,
)
_ISO_DATE_RE = re.compile(r"\b(\d{4})-(\d{2})-(\d{2})\b")


def _aggregate_authorities(sessions) -> List[SupportingAuthority]:
    """Strongest-authority union across sessions, deduped by document_id.

    We pull from `strongest_authorities` (new), falling back to the
    `authorities` alias (back-compat). Distinguishable authorities are
    not surfaced here — downstream packages should rely on what the
    research actually endorses."""
    by_doc: Dict[str, SupportingAuthority] = {}
    for s in sessions:
        candidates = s.answer.strongest_authorities or s.answer.authorities or []
        for a in candidates:
            existing = by_doc.get(a.document_id)
            if not existing or a.similarity_score > existing.similarity_score:
                by_doc[a.document_id] = a
    ranked = sorted(by_doc.values(), key=lambda a: a.similarity_score,
                    reverse=True)
    return ranked[:10]


def _timeline_from_corpus(md_docs: List[dict]) -> List[TimelineItem]:
    out: List[TimelineItem] = []
    for d in md_docs:
        dd = d.get("date_decided")
        if dd:
            out.append(TimelineItem(
                date=dd,
                event=f"Decision: {d.get('title') or d.get('filename') or 'precedent'}",
                source_document_id=d["document_id"],
                source_citation_label=f"[{d.get('filename') or d['document_id']}]",
            ))
    # De-dupe (rare but possible if two docs share the same date and title).
    seen: set[tuple[str, str]] = set()
    deduped: List[TimelineItem] = []
    for t in out:
        key = (t.date, t.event)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(t)
    # Sort newest first.
    deduped.sort(key=lambda t: t.date, reverse=True)
    return deduped[:20]


def _strength_signals(md_docs: List[dict], sessions) -> Dict[str, float]:
    if not md_docs:
        return {
            "binding_support":     0.0,
            "persuasive_support":  0.0,
            "jurisdiction_coverage": 0.0,
            "recency_score":       0.0,
            "outcome_alignment":   0.0,
            "issue_coverage":      0.0,
        }

    n = len(md_docs)
    binding = sum(1 for d in md_docs if d.get("binding_level") == "binding")
    persuasive = sum(1 for d in md_docs if d.get("binding_level") == "persuasive")

    juris_set = {d.get("jurisdiction") for d in md_docs if d.get("jurisdiction")}
    jurisdiction_coverage = clamp01(len(juris_set) / 4.0)  # nationwide ≈ 4 buckets

    # Recency: % of docs decided in the last 12 years.
    today = date.today()
    recent = 0
    for d in md_docs:
        dd = d.get("date_decided")
        if not dd:
            continue
        try:
            decided = date.fromisoformat(dd)
            if (today - decided).days <= 365 * 12:
                recent += 1
        except (ValueError, TypeError):
            continue
    recency = clamp01(recent / max(1, n))

    # Outcome alignment: % docs with a resolved outcome.
    resolved = sum(1 for d in md_docs
                   if (d.get("outcome") or "").lower() not in ("", "unknown",
                                                               "interim", None))
    outcome_alignment = clamp01(resolved / max(1, n))

    # Issue coverage: how many distinct issue tags appear.
    issue_tags: set[str] = set()
    for d in md_docs:
        for t in (d.get("issue_tags") or []):
            issue_tags.add((t or "").lower().strip())
    issue_coverage = clamp01(len(issue_tags) / 12.0)

    return {
        "binding_support":     clamp01(binding / max(1, n)),
        "persuasive_support":  clamp01(persuasive / max(1, n)),
        "jurisdiction_coverage": jurisdiction_coverage,
        "recency_score":       recency,
        "outcome_alignment":   outcome_alignment,
        "issue_coverage":      issue_coverage,
    }


def _unresolved_issues(md_docs: List[dict], sessions) -> List[str]:
    """Combines two signals into one ordered list:

    1. Issue tags present in the corpus metadata but never represented in
       a session's strongest_authorities (corpus coverage gap).
    2. Free-text `unresolved_questions` the lawyer wrote into any session
       (explicit unresolved item).

    Lawyer-written items come first because they're authored intent;
    corpus-coverage gaps come second because they're inferred.
    """
    all_tags: set[str] = set()
    for d in md_docs:
        for t in (d.get("issue_tags") or []):
            t = (t or "").strip().lower()
            if t:
                all_tags.add(t)
    covered: set[str] = set()
    for s in sessions:
        for a in (s.answer.strongest_authorities or s.answer.authorities or []):
            doc = next((d for d in md_docs
                        if d.get("document_id") == a.document_id), None)
            if not doc:
                continue
            for t in (doc.get("issue_tags") or []):
                covered.add((t or "").strip().lower())

    lawyer_items: List[str] = []
    seen_lower: set[str] = set()
    for s in sessions:
        for q in s.unresolved_questions or []:
            qq = (q or "").strip()
            if qq and qq.lower() not in seen_lower:
                lawyer_items.append(qq)
                seen_lower.add(qq.lower())

    coverage_gaps = sorted(t for t in (all_tags - covered) if t)
    return lawyer_items + coverage_gaps


def build_downstream(case_id: int | str) -> DownstreamPayload:
    ensure_case_dirs(case_id)
    md_docs = load_metadata_index(case_id)
    sessions = list_sessions(case_id)

    payload = DownstreamPayload(
        case_id=str(case_id),
        generated_at=datetime.utcnow(),
        top_authorities=_aggregate_authorities(sessions),
        timeline_items=_timeline_from_corpus(md_docs),
        case_strength_signals=_strength_signals(md_docs, sessions),
        unresolved_legal_issues=_unresolved_issues(md_docs, sessions),
        session_count=len(sessions),
        corpus_doc_count=len(md_docs),
        notes=None,
    )
    downstream_path(case_id).write_text(
        payload.model_dump_json(indent=2), encoding="utf-8",
    )
    log.info(
        "Built downstream payload: case={} authorities={} timeline={} signals={}",
        case_id, len(payload.top_authorities),
        len(payload.timeline_items), len(payload.case_strength_signals),
    )
    return payload


def load_downstream(case_id: int | str) -> DownstreamPayload | None:
    p = downstream_path(case_id)
    if not p.exists():
        return None
    try:
        return DownstreamPayload.model_validate_json(p.read_text(encoding="utf-8"))
    except Exception:
        return None
