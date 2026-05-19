"""Filter the corpus by structured criteria, then BM25-score the survivors.

The retrieval layer is intentionally dumb: it produces a list of
RetrievalHit rows keyed by chunk_id, sorted by raw BM25 score. The
reranker takes it from there.

Inputs:
  case_id, ResearchQuery
Outputs:
  list[RetrievalHit] (already filtered + scored, not yet reranked)
"""
from __future__ import annotations

from datetime import date
from typing import Dict, List, Optional, Set

from loguru import logger

from modules.research_engine.schemas.retrieval_schema import (
    ResearchQuery, RetrievalHit,
)
from modules.research_engine.services.indexing_service import (
    load_bm25, load_metadata_index,
)
from modules.evidence_vault.utils.retrieval_utils import (
    bm25_score, tokenize,
)


log = logger.bind(scope="research.retrieval")


def _docs_passing_filter(
    md_docs: List[dict], query: ResearchQuery,
) -> Set[str]:
    """Returns the set of document_ids that satisfy the structured filters
    in `query`. An empty filter on a dimension is treated as 'allow all'."""
    juris = (query.jurisdiction_filter or "").strip().lower() or None
    court_filter = {c.strip().lower() for c in query.court_filter if c}
    issue_filter = {i.strip().lower() for i in query.issue_filter if i}
    drange = query.date_range or (None, None)
    d_lo, d_hi = drange if isinstance(drange, tuple) else (None, None)

    out: Set[str] = set()
    for d in md_docs:
        if juris and (d.get("jurisdiction") or "").lower() != juris:
            continue
        if court_filter:
            ct = (d.get("court") or "").lower()
            if not any(token in ct for token in court_filter):
                continue
        if issue_filter:
            tags = {t.lower() for t in (d.get("issue_tags") or [])}
            if not (issue_filter & tags):
                continue
        if d_lo or d_hi:
            iso = d.get("date_decided")
            if not iso:
                # Documents without a parsed date are excluded only when a
                # date filter is explicitly set.
                continue
            try:
                dd = date.fromisoformat(iso)
            except (ValueError, TypeError):
                continue
            if d_lo and dd < d_lo:
                continue
            if d_hi and dd > d_hi:
                continue
        out.add(d["document_id"])
    return out


def search(case_id: int | str, query: ResearchQuery) -> List[RetrievalHit]:
    md_docs = load_metadata_index(case_id)
    if not md_docs:
        log.info("No metadata index for case={} — nothing to retrieve", case_id)
        return []
    allowed_doc_ids = _docs_passing_filter(md_docs, query)
    if not allowed_doc_ids:
        log.info("All docs filtered out for case={} query={!r}",
                 case_id, query.query_text[:80])
        return []

    bm25 = load_bm25(case_id)
    chunk_rows: List[dict] = bm25.get("chunks") or []
    tokens_by_chunk: Dict[str, List[str]] = bm25.get("tokens_by_chunk") or {}
    idf: Dict[str, float] = bm25.get("idf") or {}
    avgdl = float(bm25.get("avgdl") or 0.0)

    qtoks = tokenize(query.query_text)
    if not qtoks:
        return []

    scored: List[tuple[float, dict]] = []
    for row in chunk_rows:
        if row.get("document_id") not in allowed_doc_ids:
            continue
        toks = tokens_by_chunk.get(row.get("chunk_id"), [])
        if not toks:
            continue
        score = bm25_score(qtoks, toks, idf, avgdl)
        if score <= 0:
            continue
        scored.append((score, row))

    if not scored:
        log.info("Zero BM25 hits for case={} query={!r}",
                 case_id, query.query_text[:80])
        return []

    scored.sort(key=lambda x: x[0], reverse=True)
    scored = scored[: max(1, query.top_k * 3)]  # over-fetch for the reranker

    hits: List[RetrievalHit] = []
    for s, row in scored:
        hits.append(RetrievalHit(
            chunk_id=row["chunk_id"],
            document_id=row["document_id"],
            raw_score=float(s),
            snippet=row.get("snippet", ""),
            page_start=int(row.get("page_start") or 1),
            page_end=int(row.get("page_end") or 1),
            chunk_type=row.get("chunk_type", "unidentified"),
            paragraph_anchor=row.get("paragraph_anchor", ""),
            citation_label=row.get("citation_label", ""),
        ))
    log.info("Retrieved {} hits across {} docs for case={}",
             len(hits), len({h.document_id for h in hits}), case_id)
    return hits
