"""Multi-factor reranker.

Seven factors, each clamped to [0, 1] and weighted into a final score:

  jurisdiction_match : does the doc's jurisdiction match the query filter?
  court_rank         : coarse Indian court hierarchy (Supreme=1, ..., 0.1)
  issue_overlap      : fraction of query issue tags present in doc tags
  fact_similarity    : token overlap between query text and chunk text
  outcome_alignment  : neutral (0.5) unless the doc outcome obviously
                       favours/disfavours the query type (best-effort)
  recency            : 12-year half-life decay on date_decided
  authority_level    : binding=1.0, persuasive=0.7, informational=0.4

Default weights bias toward issue/fact match (lawyers want hits on the
substantive question), then court rank and recency, with jurisdiction and
authority as smaller multipliers. Weights are exposed so callers can tune
per query type.

Returns RankedHit rows with the full ScoreBreakdown attached, so the UI
can show *why* each precedent ranked where it did.
"""
from __future__ import annotations

from datetime import date
from typing import Dict, List

from loguru import logger

from modules.research_engine.schemas.retrieval_schema import (
    RankedHit, ResearchQuery, RetrievalHit, ScoreBreakdown,
)
from modules.research_engine.services.indexing_service import (
    load_metadata_index,
)
from modules.research_engine.utils.court_hierarchy import court_rank
from modules.research_engine.utils.score_utils import (
    clamp01, recency_score, weighted_sum,
)
from modules.evidence_vault.utils.retrieval_utils import tokenize


log = logger.bind(scope="research.rerank")


_DEFAULT_WEIGHTS: Dict[str, float] = {
    "jurisdiction_match": 0.07,
    "court_rank":         0.16,
    "issue_overlap":      0.16,
    "fact_similarity":    0.20,
    "outcome_alignment":  0.05,
    "recency":            0.12,
    "authority_level":    0.12,
    "doctrinal_relevance": 0.12,
}


_BINDING_SCORE = {
    "binding": 1.0,
    "persuasive": 0.7,
    "informational": 0.4,
}


def _years_since(iso: str | None) -> float:
    if not iso:
        return 50.0   # treat undated as old → low recency weight
    try:
        d = date.fromisoformat(iso)
    except (ValueError, TypeError):
        return 50.0
    today = date.today()
    return (today - d).days / 365.25


def _fact_similarity(query_tokens: List[str], snippet: str) -> float:
    if not snippet or not query_tokens:
        return 0.0
    body_tokens = set(tokenize(snippet))
    if not body_tokens:
        return 0.0
    q = set(query_tokens)
    overlap = len(q & body_tokens)
    return clamp01(overlap / max(1, len(q)))


def _outcome_alignment(outcome: str | None, query_type: str) -> float:
    """Neutral 0.5 — surfacing precedents with adverse outcomes is still
    valuable. We bump slightly when a fact-pattern query lines up with a
    clearly resolved outcome ("allowed" / "dismissed"), since those are
    more decision-useful for the lawyer than interim/unresolved orders."""
    if not outcome:
        return 0.5
    o = outcome.lower()
    if query_type == "fact_pattern" and o in ("allowed", "dismissed",
                                              "partly_allowed", "settled"):
        return 0.65
    if o == "unknown":
        return 0.4
    return 0.55


def _jurisdiction_match(doc_juris: str, query_juris: str | None) -> float:
    if not query_juris:
        return 0.5   # neutral when the user didn't filter
    return 1.0 if (doc_juris or "").lower() == query_juris.lower() else 0.2


def rerank(
    case_id: int | str,
    query: ResearchQuery,
    hits: List[RetrievalHit],
    weights: Dict[str, float] | None = None,
    top_k: int | None = None,
) -> List[RankedHit]:
    if not hits:
        return []

    weights = weights or _DEFAULT_WEIGHTS
    md_by_id: Dict[str, dict] = {
        d["document_id"]: d for d in load_metadata_index(case_id)
    }
    q_tokens = tokenize(query.query_text)
    q_issue_tags = {t.lower() for t in query.issue_filter if t}
    q_practice_areas = {p.lower() for p in query.practice_area_filter if p}

    ranked: List[RankedHit] = []
    for h in hits:
        doc = md_by_id.get(h.document_id) or {}
        doc_tags = {t.lower() for t in (doc.get("issue_tags") or [])}
        doc_practice = {p.lower() for p in (doc.get("practice_areas") or [])}

        issue_overlap = (
            len(q_issue_tags & doc_tags) / max(1, len(q_issue_tags))
            if q_issue_tags else
            clamp01(len(doc_tags) / 6.0)   # mild boost for well-tagged docs
        )
        # Doctrinal relevance: practice-area overlap. When the user didn't
        # supply a filter, infer doctrines from the query tokens against the
        # doc's practice areas as a soft signal.
        if q_practice_areas:
            doctrinal_relevance = (
                len(q_practice_areas & doc_practice)
                / max(1, len(q_practice_areas))
            )
        elif doc_practice and q_tokens:
            qtok_set = set(q_tokens)
            hits_in_doctrine = sum(
                1 for d in doc_practice
                if any(tok in d for tok in qtok_set) or any(d in tok for tok in qtok_set)
            )
            doctrinal_relevance = hits_in_doctrine / max(1, len(doc_practice))
        else:
            doctrinal_relevance = 0.5 if doc_practice else 0.0

        breakdown = ScoreBreakdown(
            jurisdiction_match=_jurisdiction_match(
                doc.get("jurisdiction", "India"),
                query.jurisdiction_filter,
            ),
            court_rank=court_rank(doc.get("court", "")),
            issue_overlap=clamp01(issue_overlap),
            fact_similarity=_fact_similarity(q_tokens, h.snippet),
            outcome_alignment=_outcome_alignment(doc.get("outcome"),
                                                 query.query_type),
            recency=recency_score(_years_since(doc.get("date_decided"))),
            authority_level=_BINDING_SCORE.get(
                doc.get("binding_level", "informational"), 0.4,
            ),
            doctrinal_relevance=clamp01(doctrinal_relevance),
        )
        final = weighted_sum(breakdown.model_dump(), weights)

        ranked.append(RankedHit(
            chunk_id=h.chunk_id,
            document_id=h.document_id,
            final_score=round(final, 4),
            breakdown=breakdown,
            snippet=h.snippet,
            citation_label=h.citation_label,
            page_start=h.page_start,
            page_end=h.page_end,
            chunk_type=h.chunk_type,
            paragraph_anchor=h.paragraph_anchor,
            document_title=doc.get("title", ""),
            document_citation=doc.get("citation", ""),
            document_court=doc.get("court", ""),
            document_date=doc.get("date_decided"),
            binding_level=doc.get("binding_level", "informational"),
        ))

    ranked.sort(key=lambda r: r.final_score, reverse=True)
    cut = top_k or query.top_k
    out = ranked[:cut]
    log.info("Reranked: case={} kept={} of={} top_score={:.3f}",
             case_id, len(out), len(ranked),
             out[0].final_score if out else 0.0)
    return out
