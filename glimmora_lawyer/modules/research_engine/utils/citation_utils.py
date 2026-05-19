"""Precedent citation render + light parsing.

Citation label format used across retrieval, synthesis, and the UI:

    [<filename> | p. <start>-<end> | ¶<paragraph> | chunk <K>]

The paragraph anchor block is omitted when there is no detected ¶ marker,
and the page range collapses to `p. <start>` when start == end. This keeps
labels short for the most common case (single-page citation, no ¶).
"""
from __future__ import annotations

from typing import Optional


def render_label(
    filename: str,
    page_start: int,
    page_end: Optional[int] = None,
    chunk_index: Optional[int] = None,
    paragraph_anchor: str = "",
) -> str:
    pe = page_end if page_end and page_end != page_start else None
    page_part = f"p. {page_start}-{pe}" if pe else f"p. {page_start}"
    parts = [filename, page_part]
    if paragraph_anchor:
        parts.append(f"¶{paragraph_anchor}")
    if chunk_index is not None:
        parts.append(f"chunk {chunk_index}")
    return "[" + " | ".join(parts) + "]"


def citation_chip_html(label: str) -> str:
    return (
        f'<span style="font-family: var(--font-mono); font-size: 0.7rem; '
        f'padding: 0.18rem 0.4rem; background: var(--accent-wash); '
        f'color: var(--accent); border: 1px solid var(--accent); '
        f'margin-right: 0.3rem; letter-spacing: 0.04em;">{label}</span>'
    )
