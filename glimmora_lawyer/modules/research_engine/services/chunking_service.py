"""Paragraph-aware legal chunking for precedent documents.

Pipeline:
  1. Walk pages, normalise whitespace, split each page on blank lines.
  2. Tag each raw segment with the section it falls under (headnote/facts/
     issues/arguments/ratio/holding/obiter) using regex cues common in
     Indian judgments. Falls back to "unidentified".
  3. Merge small fragments into ~60-280 word chunks; slice oversized
     blocks on word boundaries. Each chunk carries a paragraph_anchor if
     its head line starts with ¶12 / 12. / (12) / Para 12.
  4. Emit PrecedentChunk records with citation anchors. The citation label
     points back into the source PDF for grounded answers.

We deliberately do not consult the LLM here — legal chunk boundaries are
structural, and an LLM-driven splitter would be slower and harder to
reproduce across runs.
"""
from __future__ import annotations

import re
import uuid
from typing import List, Tuple

from loguru import logger

from modules.research_engine.schemas.chunk_schema import (
    ChunkCitationAnchor, PrecedentChunk,
)
from modules.research_engine.schemas.corpus_schema import PrecedentDocument
from modules.research_engine.services.persistence_service import save_chunks
from modules.research_engine.utils.citation_utils import render_label
from modules.research_engine.utils.text_utils import (
    count_chars, count_words, detect_paragraph_anchor,
    merge_small_segments, normalize_whitespace, slice_oversized,
    split_into_segments,
)


log = logger.bind(scope="research.chunking")


# ---------- Section cues ----------

# Order = decision-relevance priority. When a merged chunk contains
# multiple section cues (e.g. ARGUMENTS + RATIO + disposition phrase),
# the first cue in this list that matches *anywhere* in the chunk wins.
# Stronger cues (final disposition, holding) outrank earlier structural
# markers because they describe the operative content of the chunk.
_SECTION_CUES: list[tuple[re.Pattern, str]] = [
    (re.compile(r"\b(?:APPEAL\s+(?:IS\s+)?(?:ALLOWED|DISMISSED|"
                r"PARTLY\s+ALLOWED|DISPOSED\s+OF)|"
                r"PETITION\s+(?:IS\s+)?(?:ALLOWED|DISMISSED)|"
                r"WRIT\s+(?:IS\s+)?(?:ALLOWED|DISMISSED)|"
                r"DISPOSITION|FINAL\s+ORDER|"
                r"ORDER(?:ED)?\s+ACCORDINGLY|"
                r"DIRECTIONS?\s+ISSUED)\b", re.I),               "disposition"),
    (re.compile(r"\b(?:HELD|HOLDING|CONCLUSION|DECISION)\b", re.I),
                                                                "holding"),
    (re.compile(r"\b(?:OBITER\s+DICTA|OBITER)\b", re.I),         "obiter"),
    (re.compile(r"\b(?:HEADNOTE|HEAD\s+NOTE)\b", re.I),         "headnote"),
    (re.compile(r"\b(?:CITED|CITATIONS?|PRECEDENTS?\s+RELIED|"
                r"REFERENCES?)\b", re.I),                        "citation_block"),
    (re.compile(r"\b(?:RATIO\s+DECIDENDI|RATIO|REASONING|"
                r"ANALYSIS|DISCUSSION)\b", re.I),                "ratio"),
    (re.compile(r"\b(?:ARGUMENTS?|SUBMISSIONS?|CONTENTIONS?|"
                r"LEARNED\s+COUNSEL\s+SUBMITTED)\b", re.I),      "arguments"),
    (re.compile(r"\b(?:ISSUES?|QUESTIONS?\s+FOR\s+CONSIDERATION|"
                r"POINTS?\s+FOR\s+DETERMINATION)\b", re.I),      "issues"),
    (re.compile(r"\b(?:FACTS|FACTUAL\s+MATRIX|BRIEF\s+FACTS|"
                r"FACTUAL\s+BACKGROUND)\b", re.I),               "facts"),
]


def _infer_chunk_type(text: str, running_type: str) -> str:
    """Match section cues against the whole chunk body (capped) and return
    the highest-priority match. Falls back to the running type from the
    preceding chunk so unsignalled mid-section text inherits the surrounding
    section rather than dropping to `unidentified`."""
    # Cap at ~2000 chars — well above the 280-word chunk ceiling, but
    # cheap to scan and tolerant of any future chunk-size increase.
    body = (text or "").strip()[:2000]
    for pat, kind in _SECTION_CUES:
        if pat.search(body):
            return kind
    return running_type or "unidentified"


# ---------- Public API ----------

def _new_chunk_id() -> str:
    return "ch-" + uuid.uuid4().hex[:10]


def _new_citation_id() -> str:
    return "cit-" + uuid.uuid4().hex[:10]


def build_chunks(doc: PrecedentDocument) -> List[PrecedentChunk]:
    """Walks the document and returns a list of PrecedentChunk records."""
    if not doc.pages:
        return []

    chunks: List[PrecedentChunk] = []
    chunk_index = 0
    running_type = "unidentified"

    # First pass: gather (segment, page_number) pairs across all pages.
    raw_pairs: List[Tuple[str, int]] = []
    for page in doc.pages:
        text = normalize_whitespace(page.text)
        if not text:
            continue
        for seg in split_into_segments(text):
            raw_pairs.append((seg, page.page_number))

    if not raw_pairs:
        return []

    # Merge small fragments (page-agnostic) — page assignment uses the
    # *first* original segment that ended up inside each merged block.
    merged_pairs = _merge_with_page(raw_pairs, min_words=60, max_words=280)

    for text, page in merged_pairs:
        for piece in slice_oversized(text, max_words=280):
            chunk_type = _infer_chunk_type(piece, running_type)
            running_type = chunk_type
            anchor_para = detect_paragraph_anchor(piece) or ""
            label = render_label(
                filename=doc.filename, page_start=page, page_end=page,
                chunk_index=chunk_index, paragraph_anchor=anchor_para,
            )
            citation = ChunkCitationAnchor(
                citation_id=_new_citation_id(),
                document_id=doc.document_id,
                filename=doc.filename,
                page_start=page, page_end=page,
                chunk_index=chunk_index,
                paragraph_anchor=anchor_para,
                citation_label=label,
            )
            chunks.append(PrecedentChunk(
                chunk_id=_new_chunk_id(),
                document_id=doc.document_id,
                text=piece,
                clean_text=normalize_whitespace(piece),
                page_start=page, page_end=page,
                chunk_index=chunk_index,
                chunk_type=chunk_type,  # type: ignore[arg-type]
                paragraph_anchor=anchor_para,
                issue_tags=list(doc.meta.issue_tags),  # inherit
                word_count=count_words(piece),
                character_count=count_chars(piece),
                citation_anchor=citation,
            ))
            chunk_index += 1

    log.info("Built {} chunks for doc {} ({})",
             len(chunks), doc.document_id, doc.filename)
    return chunks


def build_and_save_chunks(case_id: int | str,
                          doc: PrecedentDocument) -> List[PrecedentChunk]:
    chunks = build_chunks(doc)
    payload = {
        "document_id": doc.document_id,
        "case_id": str(case_id),
        "chunks": [c.model_dump(mode="json") for c in chunks],
    }
    save_chunks(case_id, doc.document_id, payload)
    doc.chunks_built = True
    return chunks


# ---------- Internals ----------

def _merge_with_page(pairs: List[Tuple[str, int]],
                     min_words: int, max_words: int) -> List[Tuple[str, int]]:
    """Same greedy merge as text_utils.merge_small_segments, but carries
    each merged block's first page number alongside the text."""
    if not pairs:
        return []
    out: List[Tuple[str, int]] = []
    buf_texts: List[str] = []
    buf_page = pairs[0][1]
    buf_words = 0
    for seg, pg in pairs:
        w = count_words(seg)
        if buf_words + w <= max_words:
            if not buf_texts:
                buf_page = pg
            buf_texts.append(seg)
            buf_words += w
            if buf_words >= min_words:
                out.append(("\n\n".join(buf_texts), buf_page))
                buf_texts, buf_words = [], 0
        else:
            if buf_texts:
                out.append(("\n\n".join(buf_texts), buf_page))
                buf_texts, buf_words = [], 0
            out.append((seg, pg))
    if buf_texts:
        out.append(("\n\n".join(buf_texts), buf_page))
    return out
