"""Lightweight text metrics."""
from __future__ import annotations

import re


_WORD_RE = re.compile(r"\S+")


def count_words(text: str) -> int:
    return len(_WORD_RE.findall(text or ""))


def count_chars(text: str) -> int:
    return len(text or "")


def short_preview(text: str, limit: int = 240) -> str:
    t = (text or "").strip()
    return (t[: limit - 1] + "…") if len(t) > limit else t
