"""Per-chunk entity extraction orchestrator.

Every chunk is processed end-to-end (no time-based skipping). Throughput
targets sub-2-minute completion for typical legal PDFs by combining:

  * `gemini-2.5-flash` as the default model for `entity_extraction`
    (resolved via ai_extractor's per-stage registry) — flash returns a
    fully-structured response in ~3–10s per chunk versus 25–60s for pro.
  * Thread-pool concurrency (default 10 workers) — Vertex flash quotas
    on the standard publisher tier allow comfortably 10 QPS per region.

For a 30-chunk PDF that maths out to ≈3 batches × 10s ≈ 30s wall-clock.
Override the concurrency cap with `ENTITY_EXTRACTION_CONCURRENCY` if your
project's quota is different.
"""
from __future__ import annotations

import os
import time
import uuid
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, List, Tuple

from loguru import logger

from modules.evidence_vault.schemas.chunk_schema import ChunkRecord
from modules.evidence_vault.schemas.entity_schema import (
    EntityRecord, GeminiEntity,
)
from modules.evidence_vault.services.ai_extractor import extract_entities
from modules.evidence_vault.utils.entity_utils import normalize_value


def _new_entity_id() -> str:
    return "ent-" + uuid.uuid4().hex[:12]


def _concurrency() -> int:
    raw = (os.getenv("ENTITY_EXTRACTION_CONCURRENCY") or "10").strip()
    try:
        return max(1, min(20, int(raw)))
    except ValueError:
        return 10


def _to_entity_record(g: GeminiEntity, *, chunk: ChunkRecord,
                      document_id: str) -> EntityRecord:
    normalized = (g.normalized_value or "").strip()
    if not normalized:
        normalized = normalize_value(g.entity_type, g.value)
    return EntityRecord(
        entity_id=_new_entity_id(),
        entity_type=g.entity_type,
        value=(g.value or "").strip(),
        normalized_value=normalized,
        source_chunk_id=chunk.chunk_id,
        source_document_id=document_id,
        source_page=chunk.page_start,
        context_excerpt=(g.context_excerpt or "").strip()[:400],
        confidence=max(0.0, min(1.0, float(g.confidence or 0.0))),
    )


def _extract_one(chunk: ChunkRecord
                 ) -> Tuple[ChunkRecord, list, str, Exception | None]:
    """Worker — isolated so a single bad chunk doesn't sink the pool."""
    try:
        gemini_entities, source = extract_entities(chunk.clean_text)
        return chunk, gemini_entities, source, None
    except Exception as exc:
        return chunk, [], "regex", exc


def run_entity_extraction(
    *, document_id: str, chunks: List[ChunkRecord],
) -> Tuple[List[EntityRecord], Dict[str, List[str]], str]:
    """Returns (entities, chunk_id -> entity_ids, source_label).

    Every chunk is fully processed. Each chunk's Gemini call runs on its
    own thread (up to N at a time); result aggregation stays in chunk
    order so back-refs and entity IDs are stable across runs."""
    bound = logger.bind(scope="evidence.entity")
    all_entities: List[EntityRecord] = []
    chunk_back_refs: Dict[str, List[str]] = {}
    source_counter: Counter = Counter()

    if not chunks:
        return all_entities, chunk_back_refs, "regex"

    max_workers = min(_concurrency(), len(chunks))
    started_at = time.monotonic()
    bound.info("Doc {}: dispatching {} chunks across {} worker(s)",
               document_id, len(chunks), max_workers)

    # executor.map preserves input order in its output iterator, so we
    # iterate results aligned with `chunks`.
    with ThreadPoolExecutor(max_workers=max_workers,
                            thread_name_prefix="gemini-extract") as pool:
        for chunk, gemini_entities, source, exc in pool.map(_extract_one, chunks):
            if exc is not None:
                bound.error("Entity extraction crashed for chunk {}: {}",
                            chunk.chunk_id, exc)
            source_counter[source] += 1
            records: List[EntityRecord] = []
            for g in gemini_entities:
                try:
                    rec = _to_entity_record(g, chunk=chunk, document_id=document_id)
                except Exception as e:
                    bound.warning("Skip malformed entity in chunk {}: {}",
                                  chunk.chunk_id, e)
                    continue
                if not rec.value:
                    continue
                records.append(rec)
            if records:
                chunk_back_refs[chunk.chunk_id] = [r.entity_id for r in records]
                all_entities.extend(records)

    # Aggregate label: which source produced the majority of calls?
    source_label = source_counter.most_common(1)[0][0] if source_counter else "regex"
    elapsed = time.monotonic() - started_at
    bound.info(
        "Doc {}: chunks={} entities={} sources={} elapsed={:.1f}s",
        document_id, len(chunks), len(all_entities),
        dict(source_counter), elapsed,
    )
    return all_entities, chunk_back_refs, source_label
