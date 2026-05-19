"""Strict Answer schema for synthesised, citation-backed responses."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List

from pydantic import BaseModel, ConfigDict, Field


class SupportingSource(BaseModel):
    """One citation row attached to an answer."""
    citation_label: str
    document_id: str
    chunk_id: str = ""
    page: int = 1
    snippet: str = ""


class Answer(BaseModel):
    model_config = ConfigDict(extra="ignore")

    answer_id: str
    query: str
    intent: str
    final_answer: str
    supporting_sources: List[SupportingSource] = Field(default_factory=list)
    confidence: float = Field(ge=0.0, le=1.0, default=0.5)
    warnings: List[str] = Field(default_factory=list)
    retrieval_summary: Dict[str, int] = Field(default_factory=dict)

    # Extras (not in the strict spec but kept for the UI explainability panel)
    why_retrieved: str = ""
    next_question: str = ""
    generated_at: datetime = Field(default_factory=datetime.utcnow)
    synthesis_source: str = "regex"  # "vertex" | "aistudio" | "fallback"
