"""Find-similar precedents by document_id.

Strategy: take the most informative chunks of the source document (the
headnote and ratio/holding sections if present; otherwise top-N longest),
treat their combined text as a synthetic query, and run the standard
retrieval + reranking pipeline. The source document is excluded from the
results.

This is intentionally not a separate embedding model — same BM25 +
multi-factor reranker as `/search`. The advantage is that "similar" then
means similar in the same metric space the rest of the engine uses, so a
lawyer can reason about results consistently.
"""
from __future__ import annotations

from typing import List

from loguru import logger

from modules.research_engine.schemas.retrieval_schema import (
    RankedHit, ResearchQuery,
)
from modules.research_engine.services.indexing_service import load_bm25
from modules.research_engine.services.persistence_service import load_document
from modules.research_engine.services.retrieval_service import search
from modules.research_engine.services.reranking_service import rerank


log = logger.bind(scope="research.similarity")


# Chunk types most likely to capture a precedent's distinctive substance.
_PREFERRED_CHUNK_TYPES = ("headnote", "ratio", "holding")
_FALLBACK_TYPES = ("issues", "facts", "disposition")


def _seed_text_for_doc(case_id: int | str, document_id: str,
                       max_chars: int = 4000) -> str:
    """Returns the most informative snippets for the doc, capped at
    `max_chars`. Prefers headnote/ratio/holding; falls back to the
    longest chunks if none of those types are present."""
    bm25 = load_bm25(case_id) or {}
    rows: List[dict] = bm25.get("chunks") or []
    own = [r for r in rows if r.get("document_id") == document_id]
    if not own:
        # Last-resort fallback: pull the document's full_text and truncate.
        doc = load_document(case_id, document_id)
        return (doc.full_text or "")[:max_chars] if doc else ""

    def _by_type(types):
        return [r for r in own if (r.get("chunk_type") or "") in types]

    pool = _by_type(_PREFERRED_CHUNK_TYPES) or _by_type(_FALLBACK_TYPES) or own
    # Order by word_count desc — longer chunks usually carry more signal.
    pool.sort(key=lambda r: r.get("word_count", 0), reverse=True)

    parts: List[str] = []
    total = 0
    for r in pool:
        snippet = (r.get("snippet") or "").strip()
        if not snippet:
            continue
        if total + len(snippet) > max_chars:
            parts.append(snippet[: max_chars - total])
            break
        parts.append(snippet)
        total += len(snippet)
    return "\n\n".join(parts)


def find_similar(
    case_id: int | str,
    document_id: str,
    top_k: int = 10,
) -> List[RankedHit]:
    seed = _seed_text_for_doc(case_id, document_id)
    if not seed:
        log.info("No seed text for doc={} — returning empty", document_id)
        return []
    query = ResearchQuery(
        query_text=seed,
        query_type="fact_pattern",
        top_k=top_k * 2,   # over-fetch so we can drop the seed doc itself
    )
    hits = search(case_id, query)
    # Drop hits from the seed document so callers see *other* documents.
    hits = [h for h in hits if h.document_id != document_id]
    ranked = rerank(case_id, query, hits, top_k=top_k)
    log.info("Find-similar: case={} seed_doc={} returned={}",
             case_id, document_id, len(ranked))
    return ranked
