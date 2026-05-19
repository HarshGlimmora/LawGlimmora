"""Per-case indexes: BM25 state + filterable metadata.

We persist two index artifacts under cases/<case_id>/research/index/:

  bm25.json
    {
      "chunks": [{chunk_id, document_id, page_start, page_end, chunk_type,
                  paragraph_anchor, word_count, citation_label,
                  snippet (first 400 chars)}, ...],
      "tokens_by_chunk": {chunk_id: [tok, tok, ...], ...},
      "idf":   {tok: idf_value, ...},
      "avgdl": float,
    }

  metadata_index.json
    {
      "docs": [{document_id, title, citation, court, judges, date_decided,
                jurisdiction, practice_areas, issue_tags, outcome,
                binding_level, page_count, filename}, ...]
    }

Both are rebuilt from scratch on every call to `rebuild_index`. The user-
facing flow (UI) calls this after every successful ingest+enrich.
"""
from __future__ import annotations

import json
from typing import List

from loguru import logger

from modules.research_engine.services.persistence_service import (
    bm25_path, ensure_case_dirs, iter_documents, load_chunks,
    list_documents, metadata_index_path,
)
# Reuse Package 1's tokenizer + IDF builder — it's already battle-tested.
from modules.evidence_vault.utils.retrieval_utils import build_idf, tokenize


log = logger.bind(scope="research.index")


def _short_snippet(text: str, n: int = 400) -> str:
    t = (text or "").strip()
    return t[: n - 1] + "…" if len(t) > n else t


def rebuild_index(case_id: int | str) -> dict:
    """Rebuilds both indexes from disk-of-truth (corpus/extracted + chunks).

    Returns a small summary dict for the UI.
    """
    ensure_case_dirs(case_id)

    # 1) Metadata index — read each extracted doc once.
    md_docs: List[dict] = []
    for doc_payload in iter_documents(case_id):
        meta = doc_payload.get("meta") or {}
        md_docs.append({
            "document_id": doc_payload.get("document_id"),
            "title": meta.get("title", ""),
            "citation": meta.get("citation", ""),
            "court": meta.get("court", ""),
            "judges": meta.get("judges", []),
            "date_decided": meta.get("date_decided"),
            "jurisdiction": meta.get("jurisdiction", "India"),
            "practice_areas": meta.get("practice_areas", []),
            "issue_tags": meta.get("issue_tags", []),
            "outcome": meta.get("outcome"),
            "binding_level": meta.get("binding_level", "informational"),
            "page_count": doc_payload.get("page_count", 0),
            "filename": doc_payload.get("filename", ""),
        })
    metadata_index_path(case_id).write_text(
        json.dumps({"docs": md_docs}, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    # 2) BM25 index — collect every chunk across all docs, tokenise.
    chunk_rows: List[dict] = []
    tokens_by_chunk: dict[str, List[str]] = {}
    for doc_id in list_documents(case_id):
        payload = load_chunks(case_id, doc_id)
        if not payload:
            continue
        for c in payload.get("chunks", []):
            chunk_id = c.get("chunk_id")
            if not chunk_id:
                continue
            text = c.get("clean_text") or c.get("text") or ""
            toks = tokenize(text)
            tokens_by_chunk[chunk_id] = toks
            anchor = c.get("citation_anchor") or {}
            chunk_rows.append({
                "chunk_id": chunk_id,
                "document_id": c.get("document_id"),
                "page_start": c.get("page_start") or anchor.get("page_start"),
                "page_end":   c.get("page_end")   or anchor.get("page_end"),
                "chunk_type": c.get("chunk_type", "unidentified"),
                "paragraph_anchor": c.get("paragraph_anchor", ""),
                "word_count": c.get("word_count", 0),
                "citation_label": anchor.get("citation_label", ""),
                "snippet": _short_snippet(text, 400),
            })

    corpus = list(tokens_by_chunk.values())
    idf = build_idf(corpus) if corpus else {}
    avgdl = (sum(len(t) for t in corpus) / max(1, len(corpus))) if corpus else 0.0

    bm25_payload = {
        "chunks": chunk_rows,
        "tokens_by_chunk": tokens_by_chunk,
        "idf": idf,
        "avgdl": avgdl,
    }
    bm25_path(case_id).write_text(
        json.dumps(bm25_payload, ensure_ascii=False),
        encoding="utf-8",
    )

    summary = {
        "docs": len(md_docs),
        "chunks": len(chunk_rows),
        "vocab_size": len(idf),
        "avgdl": round(avgdl, 1),
    }
    log.info("Rebuilt index for case={}: {}", case_id, summary)
    return summary


def load_metadata_index(case_id: int | str) -> List[dict]:
    p = metadata_index_path(case_id)
    if not p.exists():
        return []
    try:
        return json.loads(p.read_text(encoding="utf-8")).get("docs", []) or []
    except Exception:
        return []


def load_bm25(case_id: int | str) -> dict:
    p = bm25_path(case_id)
    if not p.exists():
        return {"chunks": [], "tokens_by_chunk": {}, "idf": {}, "avgdl": 0.0}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {"chunks": [], "tokens_by_chunk": {}, "idf": {}, "avgdl": 0.0}
