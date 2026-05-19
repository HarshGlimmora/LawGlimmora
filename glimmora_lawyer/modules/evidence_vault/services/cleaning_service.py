"""Legal-aware page-text normalisation.

Goals: collapse whitespace, fix ligatures, kill repeated empty lines,
strip "Page X of Y"-style footers, de-hyphenate line breaks.
Non-goals: lowercasing, punctuation stripping, structure flattening,
removing legal numbering or section headings.
"""
from __future__ import annotations

import re


_LIGATURES = {
    "ﬀ": "ff", "ﬁ": "fi", "ﬂ": "fl", "ﬃ": "ffi", "ﬄ": "ffl",
    "‘": "'", "’": "'", "“": '"', "”": '"',
    "–": "-", "—": "—", "…": "...",
    " ": " ", " ": " ",  # NBSP / narrow no-break space → regular space
}

_PAGE_FOOTER_RE = re.compile(
    r"^\s*Page\s+\d+\s+of\s+\d+\s*$", re.IGNORECASE | re.MULTILINE,
)
_BARE_PAGENUM_RE = re.compile(r"^\s*\d{1,4}\s*$", re.MULTILINE)
_TRAILING_WS_RE = re.compile(r"[ \t]+$", re.MULTILINE)
_MULTI_BLANK_RE = re.compile(r"\n{3,}")
_INTRA_SPACE_RE = re.compile(r"[ \t]{2,}")
_HYPH_BREAK_RE = re.compile(r"-\n(\w)")


def clean_text(text: str) -> str:
    """Returns a normalised version of a raw page string.

    Preserves: numbering (1., (a), i., I., Section 73), section headings,
    citations, dates, paragraph boundaries, and original casing/punctuation.
    """
    if not text:
        return ""
    out = text
    for k, v in _LIGATURES.items():
        out = out.replace(k, v)
    out = _HYPH_BREAK_RE.sub(r"\1", out)
    out = _PAGE_FOOTER_RE.sub("", out)
    out = _BARE_PAGENUM_RE.sub("", out)
    out = _INTRA_SPACE_RE.sub(" ", out)
    out = _TRAILING_WS_RE.sub("", out)
    out = _MULTI_BLANK_RE.sub("\n\n", out)
    return out.strip()
