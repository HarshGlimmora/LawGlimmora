"""Citation render helpers shared by retrieval + chat surfaces."""
from __future__ import annotations

from typing import Optional


def citation_label(filename: str, page_start: int,
                   page_end: Optional[int] = None,
                   chunk_index: Optional[int] = None) -> str:
    pe = page_end if page_end and page_end != page_start else None
    page_part = f"p. {page_start}-{pe}" if pe else f"p. {page_start}"
    if chunk_index is not None:
        return f"[{filename} | {page_part} | chunk {chunk_index}]"
    return f"[{filename} | {page_part}]"


def citation_chip_html(label: str) -> str:
    return (
        f'<span style="font-family: var(--font-mono); font-size: 0.7rem; '
        f'padding: 0.2rem 0.45rem; background: var(--accent-wash); '
        f'color: var(--accent); border: 1px solid var(--accent); '
        f'margin-right: 0.35rem; letter-spacing: 0.04em;">{label}</span>'
    )
