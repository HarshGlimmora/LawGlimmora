"""Text helpers for precedent ingestion + chunking.

Two things matter here:

1. Paragraph-anchor detection. Indian judgments commonly use "¶12", "12.",
   "(12)", or "Para 12" at the start of a paragraph. We try a few patterns
   and return the first plausible match.
2. Segment splitting. Judgments are mostly long paragraphs separated by
   blank lines; we split on that and then merge short fragments so chunk
   sizes stay in a reasonable band.
"""
from __future__ import annotations

import re
from typing import List, Optional


_WORD_RE = re.compile(r"\S+")

# Order matters — most specific patterns first.
_PARA_PATTERNS: list[re.Pattern] = [
    re.compile(r"^¶\s*(\d+[A-Za-z]?)\b"),
    re.compile(r"^\(\s*(\d+[A-Za-z]?)\s*\)"),
    re.compile(r"^Para(?:graph)?\.?\s+(\d+[A-Za-z]?)\b", re.I),
    re.compile(r"^(\d{1,3})\.\s"),
]


def count_words(text: str) -> int:
    return len(_WORD_RE.findall(text or ""))


def count_chars(text: str) -> int:
    return len(text or "")


def short_preview(text: str, limit: int = 240) -> str:
    t = (text or "").strip()
    return (t[: limit - 1] + "…") if len(t) > limit else t


def detect_paragraph_anchor(text: str) -> Optional[str]:
    """Returns the paragraph number if the segment starts with a recognisable
    marker, else None."""
    head = (text or "").lstrip()[:60]
    for pat in _PARA_PATTERNS:
        m = pat.match(head)
        if m:
            return m.group(1)
    return None


def split_into_segments(text: str) -> List[str]:
    """Split on blank-line boundaries, preserving paragraph integrity.

    Falls back to single-line splits if the input has no blank lines.
    """
    if not text:
        return []
    parts = re.split(r"\n\s*\n+", text)
    parts = [p.strip() for p in parts if p and p.strip()]
    if len(parts) <= 1:
        # No blank-line boundaries — try single newlines as a last resort.
        parts = [ln.strip() for ln in text.splitlines() if ln.strip()]
    return parts


def merge_small_segments(
    segments: List[str], min_words: int = 60, max_words: int = 280,
) -> List[str]:
    """Greedy merge of small fragments so chunks live in [min, max] words.

    Anything still over `max_words` after merging is sliced on word
    boundaries by `slice_oversized` (caller's responsibility).
    """
    out: List[str] = []
    buf: List[str] = []
    buf_words = 0
    for seg in segments:
        w = count_words(seg)
        if buf_words + w <= max_words:
            buf.append(seg)
            buf_words += w
            if buf_words >= min_words:
                out.append("\n\n".join(buf))
                buf, buf_words = [], 0
        else:
            if buf:
                out.append("\n\n".join(buf))
                buf, buf_words = [], 0
            out.append(seg)
    if buf:
        out.append("\n\n".join(buf))
    return out


def slice_oversized(text: str, max_words: int = 280) -> List[str]:
    """Split a single oversized block on word boundaries."""
    words = (text or "").split()
    if len(words) <= max_words:
        return [text]
    out: List[str] = []
    for i in range(0, len(words), max_words):
        out.append(" ".join(words[i : i + max_words]))
    return out


def normalize_whitespace(text: str) -> str:
    """Collapse runs of whitespace, normalise line endings."""
    if not text:
        return ""
    t = text.replace("\r\n", "\n").replace("\r", "\n")
    t = re.sub(r"[ \t]+", " ", t)
    t = re.sub(r"\n{3,}", "\n\n", t)
    return t.strip()
