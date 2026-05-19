"""Query, retrieval, and ranking schemas."""
from __future__ import annotations

from datetime import date
from typing import List, Literal, Optional, Tuple

from pydantic import BaseModel, ConfigDict, Field


QueryType = Literal["legal_question", "fact_pattern"]


class ResearchQuery(BaseModel):
    model_config = ConfigDict(extra="ignore")

    query_text: str
    query_type: QueryType = "legal_question"
    jurisdiction_filter: Optional[str] = None
    court_filter: List[str] = Field(default_factory=list)
    date_range: Optional[Tuple[Optional[date], Optional[date]]] = None
    issue_filter: List[str] = Field(default_factory=list)
    practice_area_filter: List[str] = Field(default_factory=list)
    top_k: int = Field(default=15, ge=1, le=100)


class RetrievalHit(BaseModel):
    chunk_id: str
    document_id: str
    raw_score: float
    snippet: str
    page_start: int
    page_end: int
    chunk_type: str
    paragraph_anchor: str = ""
    citation_label: str


class ScoreBreakdown(BaseModel):
    """Each factor is a value in [0, 1] so the final score is interpretable."""
    jurisdiction_match: float = 0.0
    court_rank: float = 0.0
    issue_overlap: float = 0.0
    fact_similarity: float = 0.0
    outcome_alignment: float = 0.0
    recency: float = 0.0
    authority_level: float = 0.0
    # Doctrinal alignment between the query's practice areas (when supplied)
    # and the precedent's metadata practice areas. Distinct from issue_overlap:
    # doctrine = body of law (e.g. "contract", "constitutional"), issues =
    # specific legal questions ("specific performance", "Article 14").
    doctrinal_relevance: float = 0.0


class RankedHit(BaseModel):
    model_config = ConfigDict(extra="ignore")

    chunk_id: str
    document_id: str
    final_score: float
    breakdown: ScoreBreakdown
    snippet: str
    citation_label: str
    page_start: int
    page_end: int
    chunk_type: str
    paragraph_anchor: str = ""
    # Carried up so the synthesizer/UI never has to re-join with PrecedentMeta:
    document_title: str = ""
    document_citation: str = ""
    document_court: str = ""
    document_date: Optional[str] = None
    binding_level: str = "informational"
