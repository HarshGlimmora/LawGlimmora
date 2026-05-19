"""Entity-side of the retrieval pipeline.

Scores all entities for a query using:
  - exact-match against entity value or normalized_value (highest weight)
  - intent-driven type filter (preferred)
  - partition filter (if user set one explicitly)
  - token overlap between query and the entity's context_excerpt
The result is a list of `RetrievalResult` rows of type "entity".
"""
from __future__ import annotations

import uuid
from typing import Dict, List, Optional

from loguru import logger

from modules.evidence_vault.schemas.retrieval_schema import RetrievalResult
from modules.evidence_vault.utils.citation_utils import citation_label
from modules.evidence_vault.utils.retrieval_utils import jaccard, tokenize


def _new_result_id() -> str:
    return "res-" + uuid.uuid4().hex[:10]


def search_entities(
    *,
    query: str,
    entities: List[dict],
    chunk_by_id: Dict[str, dict],
    preferred_types: Optional[List[str]] = None,
    partition_filter: Optional[List[str]] = None,
    partition_for_type: Dict[str, str],
    top_k: int = 12,
) -> List[RetrievalResult]:
    """Returns top entity hits ranked by combined score."""
    qtoks = tokenize(query)
    qlow = (query or "").lower().strip()
    preferred = {t.upper() for t in (preferred_types or [])}
    partitions = {p for p in (partition_filter or [])}

    out: List[tuple[float, dict]] = []
    for ent in entities:
        etype = ent.get("entity_type", "")
        ptype = partition_for_type.get(etype, "")
        if partitions and ptype not in partitions:
            continue

        val_low = (ent.get("value") or "").lower()
        norm_low = (ent.get("normalized_value") or "").lower()
        ctx_low = (ent.get("context_excerpt") or "").lower()
        ctx_toks = tokenize(ent.get("context_excerpt") or "")

        score = 0.0
        # Exact substring matches are gold for entity search.
        if qlow and (qlow in val_low or qlow in norm_low):
            score += 3.0
        # Token overlap with the surrounding context.
        score += jaccard(qtoks, ctx_toks) * 1.2
        # Soft token overlap with value/normalized.
        score += jaccard(qtoks, tokenize(val_low) + tokenize(norm_low)) * 1.5
        # Intent boost.
        if preferred and etype in preferred:
            score += 1.2
        # Confidence as a tiebreaker.
        score += 0.3 * float(ent.get("confidence", 0.0))

        if score <= 0:
            continue
        out.append((score, ent))

    out.sort(key=lambda x: x[0], reverse=True)
    out = out[:top_k]

    results: List[RetrievalResult] = []
    top_score = out[0][0] if out else 1.0
    for raw_score, ent in out:
        norm_conf = max(0.0, min(1.0, raw_score / (top_score or 1.0)))
        chunk = chunk_by_id.get(ent.get("source_chunk_id", ""), {}) or {}
        anchor = chunk.get("citation_anchor") or {}
        filename = anchor.get("filename") or ent.get("source_document_id", "")
        page_start = anchor.get("page_start") or ent.get("source_page", 1)
        page_end = anchor.get("page_end") or page_start
        chunk_idx = anchor.get("chunk_index")
        label = citation_label(filename, page_start, page_end, chunk_idx)
        reason = (
            f"entity_type={ent.get('entity_type')} "
            + (f"intent-preferred " if ent.get('entity_type') in preferred else "")
            + (f"partition={ent.get('entity_type') and 'matched' or ''}"
               if partition_filter else "")
        ).strip()
        title = f"{ent.get('entity_type')} · {ent.get('value', '')}"
        snippet = ent.get("context_excerpt") or ent.get("normalized_value") or ent.get("value") or ""
        results.append(RetrievalResult(
            result_id=_new_result_id(),
            result_type="entity",
            title=title[:200],
            snippet=snippet[:400],
            source_document_id=ent.get("source_document_id", ""),
            source_chunk_id=ent.get("source_chunk_id", ""),
            source_page=int(page_start or 1),
            citation_label=label,
            confidence=round(norm_conf, 3),
            reason_retrieved=reason or "entity match",
        ))
    logger.bind(scope="evidence.retrieval").info(
        "Entity search: query={!r} preferred={} partitions={} hits={}",
        (query or "")[:60], list(preferred) or "-", list(partitions) or "-",
        len(results),
    )
    return results
