"""Chunk schema for precedent corpus.

Each chunk carries a paragraph_anchor (¶ marker if detectable) and a
chunk_type tag drawn from the legal-judgment vocabulary. Citations resolve
to <filename | p.X–Y | ¶N | chunk K> labels.
"""
from __future__ import annotations

from typing import List, Literal

from pydantic import BaseModel, ConfigDict, Field


ChunkType = Literal[
    "headnote",
    "facts",
    "issues",
    "arguments",
    "ratio",
    "holding",
    "obiter",
    "citation_block",
    "disposition",      # "Appeal allowed", "Order accordingly", final disposition lines
    "unidentified",
]


CHUNK_TYPES: List[str] = [
    "headnote", "facts", "issues", "arguments",
    "ratio", "holding", "obiter", "citation_block",
    "disposition", "unidentified",
]


class ChunkCitationAnchor(BaseModel):
    citation_id: str
    document_id: str
    filename: str
    page_start: int = Field(ge=1)
    page_end: int = Field(ge=1)
    chunk_index: int = Field(ge=0)
    paragraph_anchor: str = ""
    citation_label: str


class PrecedentChunk(BaseModel):
    model_config = ConfigDict(extra="ignore")

    chunk_id: str
    document_id: str
    text: str
    clean_text: str
    page_start: int = Field(ge=1)
    page_end: int = Field(ge=1)
    chunk_index: int = Field(ge=0)
    chunk_type: ChunkType = "unidentified"
    paragraph_anchor: str = ""
    issue_tags: List[str] = Field(default_factory=list)
    word_count: int = 0
    character_count: int = 0
    citation_anchor: ChunkCitationAnchor
    confidence: float = 0.92
