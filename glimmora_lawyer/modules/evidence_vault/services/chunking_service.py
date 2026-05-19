"""Hybrid legal chunking: structural segmentation + size normalization.

Pipeline (per document):
  1. Assemble full document text from per-page clean_text (track page bounds).
  2. Find structural segments (headings, numbered clauses, sections, etc.).
  3. Split oversized segments at sentence boundaries.
  4. Merge undersized adjacent segments.
  5. Build ChunkRecord with chunk-level citation anchor and inferred type.
"""
from __future__ import annotations

import uuid
from typing import List, Tuple

from loguru import logger

from modules.evidence_vault.schemas.chunk_schema import (
    ChunkCitationAnchor, ChunkRecord,
)
from modules.evidence_vault.schemas.evidence_schema import CanonicalEvidence
from modules.evidence_vault.services.citation_service import build_chunk_citation
from modules.evidence_vault.utils.chunk_utils import (
    find_structural_segments, infer_chunk_type, make_embedding_ready,
    map_chunk_to_pages, merge_undersized, split_oversized,
)
from modules.evidence_vault.utils.text_utils import count_chars, count_words


PAGE_JOIN = "\n\n"
TARGET_MIN_WORDS = 60
TARGET_MAX_WORDS = 800


def _assemble(doc: CanonicalEvidence) -> Tuple[str, List[Tuple[int, int, int]]]:
    parts: List[str] = []
    page_bounds: List[Tuple[int, int, int]] = []
    cursor = 0
    for p in doc.pages:
        start = cursor
        body = p.clean_text or ""
        parts.append(body)
        cursor += len(body)
        page_bounds.append((p.page_number, start, cursor))
        parts.append(PAGE_JOIN)
        cursor += len(PAGE_JOIN)
    return "".join(parts), page_bounds


def run_chunking(doc: CanonicalEvidence) -> List[ChunkRecord]:
    """Return a list of ChunkRecord for the given canonical document.

    The function does not mutate the input; the orchestrator decides where
    to attach the results (per-doc canonical + case-level aggregate)."""
    bound = logger.bind(scope="evidence.chunking")
    if not doc.pages:
        bound.info("Document {} has no pages — skipping chunking.",
                   doc.document.document_id)
        return []

    full_text, page_bounds = _assemble(doc)

    structural = find_structural_segments(full_text)
    bound.info("Doc {}: structural segments={}",
               doc.document.document_id, len(structural))

    sized = split_oversized(full_text, structural, max_words=TARGET_MAX_WORDS)
    sized = merge_undersized(full_text, sized,
                             min_words=TARGET_MIN_WORDS,
                             max_words=TARGET_MAX_WORDS)
    bound.info("Doc {}: chunks after sizing={}",
               doc.document.document_id, len(sized))

    chunks: List[ChunkRecord] = []
    for idx, (cs, ce) in enumerate(sized):
        text = full_text[cs:ce]
        if not text.strip():
            continue
        page_start, page_end = map_chunk_to_pages(cs, ce, page_bounds)
        chunk_id = "chk-" + uuid.uuid4().hex[:12]
        citation = build_chunk_citation(
            document_id=doc.document.document_id,
            filename=doc.document.filename,
            page_start=page_start, page_end=page_end,
            chunk_index=idx, char_start=cs, char_end=ce,
        )
        clean = text.strip()
        chunks.append(ChunkRecord(
            chunk_id=chunk_id,
            document_id=doc.document.document_id,
            page_start=page_start,
            page_end=page_end,
            chunk_index=idx,
            chunk_type=infer_chunk_type(clean),  # type: ignore[arg-type]
            text=text,
            clean_text=clean,
            embedding_ready_text=make_embedding_ready(clean),
            word_count=count_words(clean),
            character_count=count_chars(clean),
            citation_anchor=citation,
            entities=[],
            claims=[],
            confidence=0.9,
        ))

    bound.info("Doc {}: produced {} chunks", doc.document.document_id, len(chunks))
    return chunks
