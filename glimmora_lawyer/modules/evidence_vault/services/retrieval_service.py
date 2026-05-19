"""Main retrieval pipeline. Builds a RetrievalContext for the synthesiser.

Order (matches spec):
  1. Load chunks / entities / partitions / contradictions / missing-evidence
  2. Classify user query
  3. Map query to entity types and partitions
  4. Retrieve entity matches
  5. Retrieve chunk matches (BM25-ish)
  6. Retrieve contradictions / missing-evidence (only if those indexes exist)
  7. Rank results
  8. Persist debug payload + entity-search cache + retrieval_index (on first run)
  9. Return RetrievalContext
"""
from __future__ import annotations

import uuid
from typing import Dict, List, Optional

from loguru import logger

from modules.evidence_vault.schemas.entity_schema import PARTITION_FOR_TYPE
from modules.evidence_vault.schemas.retrieval_schema import (
    RetrievalContext, RetrievalMode, RetrievalResult,
)
from modules.evidence_vault.services.chunk_persistence_service import (
    load_case_chunks, load_case_entities, load_case_partitions,
)
from modules.evidence_vault.services.entity_rag_service import search_entities
from modules.evidence_vault.services.persistence_service import (
    case_evidence_root,
)
from modules.evidence_vault.services.query_classifier_service import (
    classify, intent_filters,
)
from modules.evidence_vault.services.retrieval_persistence_service import (
    append_search_cache, load_retrieval_index, write_retrieval_debug,
    write_retrieval_index,
)
from modules.evidence_vault.utils.citation_utils import citation_label
from modules.evidence_vault.utils.retrieval_utils import (
    bm25_score, build_idf, normalize_scores, tokenize,
)

log = logger.bind(scope="evidence.retrieval")


def _new_result_id() -> str:
    return "res-" + uuid.uuid4().hex[:10]


def _build_lookup_maps(case_id: int | str):
    """Returns (chunks_payload, entities_payload, partitions_payload, chunk_by_id)."""
    chunks_payload = load_case_chunks(case_id) or {}
    entities_payload = load_case_entities(case_id) or {}
    partitions_payload = load_case_partitions(case_id) or {}

    all_chunks: List[dict] = chunks_payload.get("chunks") or []
    chunk_by_id = {c["chunk_id"]: c for c in all_chunks}
    return chunks_payload, entities_payload, partitions_payload, chunk_by_id


# ---------- Chunk search (BM25) ----------

def _search_chunks(*, query: str, chunks: List[dict],
                   intent_types: List[str], top_k: int = 8) -> List[RetrievalResult]:
    if not chunks:
        return []
    qtoks = tokenize(query)
    if not qtoks:
        return []
    corpus = [tokenize(c.get("clean_text") or c.get("text") or "") for c in chunks]
    idf = build_idf(corpus)
    avgdl = sum(len(t) for t in corpus) / max(1, len(corpus))

    intent_chunk_types = set()
    # Soft preference: timeline_query → timeline chunks, party_query → witness chunks, etc.
    # (Optional — we just nudge ranking.)

    scored: List[tuple[float, dict]] = []
    for c, toks in zip(chunks, corpus):
        score = bm25_score(qtoks, toks, idf, avgdl)
        if score <= 0:
            continue
        # Soft chunk-type alignment boost
        ctype = (c.get("chunk_type") or "").lower()
        if "timeline" in intent_chunk_types and ctype == "timeline":
            score *= 1.15
        scored.append((score, c))

    if not scored:
        return []
    scored.sort(key=lambda x: x[0], reverse=True)
    scored = scored[:top_k]
    scored = normalize_scores(scored)

    results: List[RetrievalResult] = []
    for conf, c in scored:
        anchor = c.get("citation_anchor") or {}
        filename = anchor.get("filename") or ""
        page_start = anchor.get("page_start") or c.get("page_start") or 1
        page_end = anchor.get("page_end") or c.get("page_end") or page_start
        chunk_idx = anchor.get("chunk_index", c.get("chunk_index"))
        label = citation_label(filename, page_start, page_end, chunk_idx)
        snippet = (c.get("clean_text") or "")[:400]
        results.append(RetrievalResult(
            result_id=_new_result_id(),
            result_type="chunk",
            title=f"{c.get('chunk_type', 'chunk')} · {filename} p.{page_start}",
            snippet=snippet,
            source_document_id=c.get("document_id", ""),
            source_chunk_id=c.get("chunk_id", ""),
            source_page=int(page_start or 1),
            citation_label=label,
            confidence=round(float(conf), 3),
            reason_retrieved="BM25 token overlap with chunk body",
        ))
    log.info("Chunk search: query={!r} hits={}", (query or "")[:60], len(results))
    return results


# ---------- Optional contradictions / missing ----------

def _load_contradictions(case_id: int | str) -> List[dict]:
    """Defensive load — returns [] if the contradictions index isn't built yet."""
    p = case_evidence_root(case_id) / "reports" / "contradictions.json"
    if not p.exists():
        return []
    import json as _json
    try:
        return _json.loads(p.read_text(encoding="utf-8")).get("items", [])
    except Exception:
        return []


def _load_missing(case_id: int | str) -> List[dict]:
    p = case_evidence_root(case_id) / "reports" / "missing_evidence.json"
    if not p.exists():
        return []
    import json as _json
    try:
        return _json.loads(p.read_text(encoding="utf-8")).get("items", [])
    except Exception:
        return []


def _search_contradictions(query: str, items: List[dict],
                           top_k: int = 4) -> List[RetrievalResult]:
    if not items:
        return []
    qtoks = set(tokenize(query))
    out: List[tuple[float, dict]] = []
    for it in items:
        body = " ".join([
            it.get("summary", ""), it.get("explanation", ""), it.get("kind", ""),
        ])
        score = len(qtoks & set(tokenize(body)))
        if score:
            out.append((float(score), it))
    out.sort(key=lambda x: x[0], reverse=True)
    out = out[:top_k]
    results: List[RetrievalResult] = []
    for s, it in out:
        results.append(RetrievalResult(
            result_id=_new_result_id(),
            result_type="contradiction",
            title=it.get("summary", "")[:200],
            snippet=it.get("explanation", "")[:400],
            source_document_id="", source_chunk_id="",
            source_page=1,
            citation_label=f"[contradiction · {it.get('id', '')}]",
            confidence=min(1.0, s / 4.0),
            reason_retrieved="contradiction record matched query tokens",
        ))
    return results


def _search_missing(query: str, items: List[dict],
                    top_k: int = 4) -> List[RetrievalResult]:
    if not items:
        return []
    qtoks = set(tokenize(query))
    out: List[tuple[float, dict]] = []
    for it in items:
        body = " ".join([it.get("category", ""), it.get("recommendation", ""),
                         it.get("why_it_matters", "")])
        score = len(qtoks & set(tokenize(body)))
        if score:
            out.append((float(score), it))
    out.sort(key=lambda x: x[0], reverse=True)
    out = out[:top_k]
    results: List[RetrievalResult] = []
    for s, it in out:
        results.append(RetrievalResult(
            result_id=_new_result_id(),
            result_type="missing_evidence",
            title=it.get("category", "")[:200],
            snippet=it.get("recommendation", "")[:400],
            source_document_id="", source_chunk_id="",
            source_page=1,
            citation_label=f"[missing · {it.get('category', '')}]",
            confidence=min(1.0, s / 4.0),
            reason_retrieved="missing-evidence record matched query tokens",
        ))
    return results


# ---------- Ranking ----------

def _rank(mode: RetrievalMode,
          ent: List[RetrievalResult],
          chk: List[RetrievalResult],
          contr: List[RetrievalResult],
          miss: List[RetrievalResult],
          top_n: int = 10) -> List[RetrievalResult]:
    if mode == "entity-first":
        weight = {"entity": 1.0, "chunk": 0.55,
                  "contradiction": 0.9, "missing_evidence": 0.9}
    elif mode == "chunk-first":
        weight = {"entity": 0.55, "chunk": 1.0,
                  "contradiction": 0.9, "missing_evidence": 0.9}
    else:  # hybrid
        weight = {"entity": 0.85, "chunk": 0.85,
                  "contradiction": 0.95, "missing_evidence": 0.95}
    combined: List[tuple[float, RetrievalResult]] = []
    for arr in (ent, chk, contr, miss):
        for r in arr:
            combined.append((r.confidence * weight[r.result_type], r))
    combined.sort(key=lambda x: x[0], reverse=True)
    return [r for _, r in combined[:top_n]]


# ---------- Public entry ----------

def build_retrieval_index_if_missing(case_id: int | str) -> None:
    """Cheap idempotent write — rebuilt on every ingest, but called here as a
    safety net in case the user lands on the chat tab before re-ingest."""
    if load_retrieval_index(case_id):
        return
    chunks_payload, entities_payload, partitions_payload, _ = _build_lookup_maps(case_id)
    chunks = chunks_payload.get("chunks") or []
    entities = entities_payload.get("entities") or []
    chunks_summary = [{
        "chunk_id": c.get("chunk_id"),
        "document_id": c.get("document_id"),
        "page_start": (c.get("citation_anchor") or {}).get("page_start"),
        "page_end": (c.get("citation_anchor") or {}).get("page_end"),
        "chunk_type": c.get("chunk_type"),
        "word_count": c.get("word_count"),
    } for c in chunks]
    entities_summary = [{
        "entity_id": e.get("entity_id"), "entity_type": e.get("entity_type"),
        "value": e.get("value"),
        "normalized_value": e.get("normalized_value"),
        "source_chunk_id": e.get("source_chunk_id"),
        "source_page": e.get("source_page"),
        "confidence": e.get("confidence"),
    } for e in entities]
    partitions_summary = {p["partition_type"]: len(p.get("entities") or [])
                          for p in (partitions_payload.get("partitions") or [])}
    write_retrieval_index(
        case_id,
        chunks_summary=chunks_summary,
        entities_summary=entities_summary,
        partitions_summary=partitions_summary,
    )


def retrieve(
    *,
    case_id: int | str,
    query: str,
    mode: RetrievalMode = "hybrid",
    partition_filter: Optional[List[str]] = None,
    top_n: int = 10,
) -> RetrievalContext:
    log.info("Retrieve: case={} mode={} partitions={} query={!r}",
             case_id, mode, partition_filter or "-", (query or "")[:120])

    intent = classify(query)
    mapping = intent_filters(intent)
    preferred_types: List[str] = mapping.get("types", [])
    # If user didn't set an explicit partition filter, use the intent's mapping.
    effective_partitions = partition_filter or mapping.get("partitions") or None

    chunks_payload, entities_payload, partitions_payload, chunk_by_id = \
        _build_lookup_maps(case_id)
    all_chunks: List[dict] = chunks_payload.get("chunks") or []
    all_entities: List[dict] = entities_payload.get("entities") or []

    build_retrieval_index_if_missing(case_id)

    ent_hits = search_entities(
        query=query,
        entities=all_entities,
        chunk_by_id=chunk_by_id,
        preferred_types=preferred_types,
        partition_filter=effective_partitions,
        partition_for_type=PARTITION_FOR_TYPE,
        top_k=12,
    )
    chk_hits = _search_chunks(
        query=query, chunks=all_chunks,
        intent_types=preferred_types, top_k=10,
    )
    contr_hits: List[RetrievalResult] = []
    miss_hits: List[RetrievalResult] = []
    if intent in ("contradiction_reference_query", "general_case_question"):
        contr_hits = _search_contradictions(query, _load_contradictions(case_id))
    if intent in ("missing_evidence_query", "general_case_question"):
        miss_hits = _search_missing(query, _load_missing(case_id))

    ranked = _rank(mode, ent_hits, chk_hits, contr_hits, miss_hits, top_n=top_n)

    ctx = RetrievalContext(
        query=query, intent=intent, mode=mode,
        partition_filter=list(effective_partitions) if effective_partitions else None,
        entity_hits=ent_hits, chunk_hits=chk_hits,
        contradiction_hits=contr_hits, missing_hits=miss_hits,
        all_results=ranked,
        debug={
            "preferred_types": preferred_types,
            "total_entities_in_case": len(all_entities),
            "total_chunks_in_case": len(all_chunks),
            "contradictions_index_present": bool(_load_contradictions(case_id)),
            "missing_index_present": bool(_load_missing(case_id)),
        },
    )

    write_retrieval_debug(case_id, ctx)
    append_search_cache(
        case_id, query=query, intent=intent,
        entity_hits=[r.model_dump(mode="json") for r in ent_hits[:10]],
    )
    log.info(
        "Retrieved: entities={} chunks={} contradictions={} missing={} ranked={}",
        len(ent_hits), len(chk_hits), len(contr_hits), len(miss_hits), len(ranked),
    )
    return ctx
