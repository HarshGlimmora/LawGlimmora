"""Chunk + chunk-level citation anchor schemas."""
from __future__ import annotations

from typing import Any, List, Literal

from pydantic import BaseModel, ConfigDict, Field


ChunkType = Literal[
    "facts",
    "procedural",
    "witness_statement",
    "allegation",
    "agreement_clause",
    "timeline",
    "court_order",
    "prayer",
    "annexure",
    "evidence_reference",
    "legal_argument",
    "unidentified",
]


CHUNK_TYPES: List[str] = [
    "facts", "procedural", "witness_statement", "allegation",
    "agreement_clause", "timeline", "court_order", "prayer",
    "annexure", "evidence_reference", "legal_argument", "unidentified",
]


class ChunkCitationAnchor(BaseModel):
    citation_id: str
    document_id: str
    filename: str
    page_start: int = Field(ge=1)
    page_end: int = Field(ge=1)
    chunk_index: int = Field(ge=0)
    char_start: int = Field(ge=0)
    char_end: int = Field(ge=0)
    citation_label: str


class ChunkRecord(BaseModel):
    model_config = ConfigDict(extra="ignore")

    chunk_id: str
    document_id: str
    page_start: int = Field(ge=1)
    page_end: int = Field(ge=1)
    chunk_index: int = Field(ge=0)
    chunk_type: ChunkType = "unidentified"
    text: str
    clean_text: str
    embedding_ready_text: str
    word_count: int = 0
    character_count: int = 0
    citation_anchor: ChunkCitationAnchor
    entities: List[str] = Field(default_factory=list)   # entity_ids
    claims: List[Any] = Field(default_factory=list)     # reserved
    confidence: float = 0.95
