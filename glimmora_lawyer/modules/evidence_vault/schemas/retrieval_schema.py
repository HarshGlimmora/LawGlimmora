"""Retrieval result + retrieval context schemas."""
from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


ResultType = Literal["entity", "chunk", "contradiction", "missing_evidence"]


RetrievalMode = Literal["entity-first", "chunk-first", "hybrid"]


QueryIntent = Literal[
    "entity_query",
    "timeline_query",
    "party_query",
    "law_section_query",
    "clause_query",
    "evidence_query",
    "contradiction_reference_query",
    "missing_evidence_query",
    "general_case_question",
]


SUGGESTED_PROMPTS: List[str] = [
    "Show all dates in this case",
    "Which evidence supports the complaint?",
    "Which sections are referenced?",
    "What pages mention the accused?",
    "What is the strongest evidence?",
    "What is inconsistent in the file?",
    "What is missing from the evidence set?",
]


class RetrievalResult(BaseModel):
    """One retrieved item (entity, chunk, contradiction, or missing-evidence)."""
    model_config = ConfigDict(extra="ignore")

    result_id: str
    result_type: ResultType
    title: str
    snippet: str
    source_document_id: str
    source_chunk_id: str = ""
    source_page: int = 1
    citation_label: str
    confidence: float = Field(ge=0.0, le=1.0, default=0.5)
    reason_retrieved: str = ""


class RetrievalContext(BaseModel):
    """Bundle of everything the synthesiser needs to write a grounded answer."""
    query: str
    intent: QueryIntent
    mode: RetrievalMode
    partition_filter: Optional[List[str]] = None

    entity_hits: List[RetrievalResult] = Field(default_factory=list)
    chunk_hits: List[RetrievalResult] = Field(default_factory=list)
    contradiction_hits: List[RetrievalResult] = Field(default_factory=list)
    missing_hits: List[RetrievalResult] = Field(default_factory=list)
    all_results: List[RetrievalResult] = Field(default_factory=list)

    debug: Dict[str, Any] = Field(default_factory=dict)
