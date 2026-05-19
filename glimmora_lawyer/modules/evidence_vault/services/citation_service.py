"""Citation anchor builder.

Page-level anchors land on PageRecord (Phase 1).
Chunk-level anchors land on ChunkRecord (Phase 2).
"""
from __future__ import annotations

from modules.evidence_vault.schemas.chunk_schema import ChunkCitationAnchor
from modules.evidence_vault.schemas.evidence_schema import CitationAnchor
from modules.evidence_vault.utils.file_utils import new_citation_id


def build_page_citation(*, document_id: str, filename: str,
                        page_number: int) -> CitationAnchor:
    return CitationAnchor(
        citation_id=new_citation_id(),
        document_id=document_id,
        filename=filename,
        page_number=page_number,
        citation_label=f"[{filename} | p.{page_number}]",
    )


def build_chunk_citation(*, document_id: str, filename: str,
                         page_start: int, page_end: int,
                         chunk_index: int,
                         char_start: int, char_end: int) -> ChunkCitationAnchor:
    page_label = (f"p.{page_start}-{page_end}" if page_end > page_start
                  else f"p.{page_start}")
    return ChunkCitationAnchor(
        citation_id=new_citation_id(),
        document_id=document_id,
        filename=filename,
        page_start=page_start,
        page_end=page_end,
        chunk_index=chunk_index,
        char_start=char_start,
        char_end=char_end,
        citation_label=f"[{filename} | {page_label} | chunk {chunk_index}]",
    )
