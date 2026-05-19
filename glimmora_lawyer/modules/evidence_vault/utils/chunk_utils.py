"""Chunking-internal helpers: structural boundaries, size split, type inference,
page mapping, embedding-ready text."""
from __future__ import annotations

import re
from typing import List, Tuple

from modules.evidence_vault.utils.text_utils import count_words


# ---- Structural boundary patterns ----
# Each match marks the START of a new structural segment.
_BOUNDARY_RE = re.compile(
    r"""
    (?:
        ^\s*\d+\.\s+\S                                  # "1. word"
      | ^\s*\d+\.\d+(?:\.\d+)*\s+\S                     # "1.1 word"
      | ^\s*\(?[a-zA-Z]\)\s+\S                          # "(a) word"
      | ^\s*[Ss]ection\s+\d+[A-Za-z]*(?:\(\d+\))?       # "Section 4(a)"
      | ^\s*Sec\.\s*\d+                                 # "Sec. 17"
      | ^\s*[Cc]lause\s+\d+(?:\.\d+)*                   # "Clause 7"
      | ^\s*[Aa]rticle\s+\d+[A-Za-z]*                   # "Article 21"
      | ^\s*[Rr]ule\s+\d+                               # "Rule 11"
      | ^\s*(?:EXHIBIT|Exhibit)\s+[A-Z0-9-]+            # "Exhibit A1"
      | ^\s*(?:ANNEXURE|Annexure)\s+[A-Z0-9-]+
      | ^\s*ANNEXURE\b
      | ^\s*PRAYER\b
      | ^\s*FACTS(?:\s+OF\s+THE\s+CASE)?\b
      | ^\s*WITNESS(?:ES)?\b
      | ^\s*PARTIES\b
      | ^\s*GROUNDS\b
      | ^\s*RELIEF(?:\s+SOUGHT)?\b
      | ^\s*PROCEDURAL\s+HISTORY\b
      | ^\s*IN\s+THE\s+(?:SUPREME\s+COURT|HIGH\s+COURT|COURT\s+OF)\b
      | ^\s*BEFORE\s+THE\b
    )
    """,
    re.VERBOSE | re.MULTILINE,
)


def find_structural_segments(text: str) -> List[Tuple[int, int]]:
    """Returns a list of (start_char, end_char) for each structural segment.
    Always covers the full text — gaps before the first boundary go into a
    leading 'prelude' segment.
    """
    if not text:
        return []
    matches = list(_BOUNDARY_RE.finditer(text))
    if not matches:
        return [(0, len(text))]

    segments: List[Tuple[int, int]] = []
    first = matches[0].start()
    if first > 0:
        prelude = text[:first].strip()
        if prelude:
            segments.append((0, first))

    for i, m in enumerate(matches):
        s = m.start()
        e = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        if text[s:e].strip():
            segments.append((s, e))
    return segments


_SENT_END_RE = re.compile(r"(?<=[.!?])\s+(?=[A-Z(\"'\[])")


def split_oversized(text: str, segments: List[Tuple[int, int]],
                    max_words: int = 800) -> List[Tuple[int, int]]:
    """Walk each structural segment; split at sentence boundaries inside the
    same original text so char offsets remain absolute and honest."""
    out: List[Tuple[int, int]] = []
    for (s, e) in segments:
        body = text[s:e]
        if count_words(body) <= max_words:
            out.append((s, e))
            continue
        # Iterate sentence ends within [s, e)
        cursor = s
        buf_start = s
        buf_words = 0
        for m in _SENT_END_RE.finditer(text, pos=s, endpos=e):
            sent_end = m.end()
            buf_words += count_words(text[cursor:sent_end])
            cursor = sent_end
            if buf_words >= max_words:
                out.append((buf_start, sent_end))
                buf_start = sent_end
                buf_words = 0
        if buf_start < e:
            out.append((buf_start, e))
    return out


def merge_undersized(text: str, segments: List[Tuple[int, int]],
                     min_words: int = 60, max_words: int = 800) -> List[Tuple[int, int]]:
    """Greedily merge consecutive small segments forward, capped by max_words."""
    if not segments:
        return segments
    out: List[Tuple[int, int]] = []
    cur_s, cur_e = segments[0]
    for (s, e) in segments[1:]:
        cur_w = count_words(text[cur_s:cur_e])
        next_w = count_words(text[s:e])
        if cur_w < min_words and (cur_w + next_w) <= max_words:
            cur_e = e
        else:
            out.append((cur_s, cur_e))
            cur_s, cur_e = s, e
    out.append((cur_s, cur_e))
    return out


# ---- Page mapping ----

def map_chunk_to_pages(char_start: int, char_end: int,
                       page_bounds: List[Tuple[int, int, int]]) -> Tuple[int, int]:
    """Given char offsets in the assembled doc text and page boundary list of
    (page_number, start_char, end_char), return (page_start, page_end)."""
    ps, pe = 1, 1
    for (page_num, ps_char, pe_char) in page_bounds:
        if ps_char <= char_start < pe_char:
            ps = page_num
        if ps_char < char_end <= pe_char:
            pe = page_num
        if char_start >= pe_char:
            ps = page_num
            pe = page_num
        if char_end > pe_char:
            pe = page_num
    if pe < ps:
        pe = ps
    return ps, pe


# ---- Chunk-type inference (cheap rule-based) ----

_TYPE_RULES: List[tuple[str, re.Pattern]] = [
    ("prayer",            re.compile(r"\bPRAYER\b|\bpray(?:s|ed)?\b|relief\s+sought", re.I)),
    ("annexure",          re.compile(r"\b(?:ANNEXURE|Exhibit|EXHIBIT)\b", re.I)),
    ("witness_statement", re.compile(r"\b(PW[-\s]?\d+|DW[-\s]?\d+|witness(?:es)?|deposed)\b", re.I)),
    ("agreement_clause",  re.compile(r"\b[Cc]lause\s+\d", re.I)),
    ("court_order",       re.compile(r"\b(?:order|directive|directed|ruling|judgment|judgement)\b", re.I)),
    ("procedural",        re.compile(r"\b(?:filed|filing|summons|notice|hearing|reply|served|arrest)\b", re.I)),
    ("legal_argument",    re.compile(r"\b(?:Section|Article|Rule)\s+\d", re.I)),
    ("allegation",        re.compile(r"\b(?:alleged|alleges|submits|denies|contends)\b", re.I)),
    ("timeline",          re.compile(
        r"\b(\d{1,2}[-/.]\d{1,2}[-/.]\d{2,4}|"
        r"\d{1,2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{4})\b",
        re.I)),
    ("facts",             re.compile(r"\bFACTS\b|\bbackground\b", re.I)),
]


def infer_chunk_type(text: str) -> str:
    if not text or not text.strip():
        return "unidentified"
    for label, pat in _TYPE_RULES:
        if pat.search(text):
            return label
    return "unidentified"


# ---- Embedding-ready text ----

_WS_RE = re.compile(r"\s+")


def make_embedding_ready(text: str) -> str:
    """Aggressively flat single-line form for vector indexing (later phase)."""
    return _WS_RE.sub(" ", (text or "").strip())
