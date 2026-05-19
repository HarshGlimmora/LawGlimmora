"""Answer + supporting authorities schema."""
from __future__ import annotations

from datetime import datetime
from typing import Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


SynthesisSource = Literal["vertex", "aistudio", "fallback"]
AuthorityTier = Literal["strongest", "distinguishable"]


class SupportingAuthority(BaseModel):
    """A single precedent surfaced as relevant to the query.

    `tier` separates the precedents the synthesizer relies on
    ("strongest") from those it flags as weak or distinguishable
    ("distinguishable"). `distinguishing_reason` is only populated for the
    latter tier — it tells the lawyer *why* this precedent is unlikely to
    apply (different forum, different facts, narrower holding, etc.).
    """
    model_config = ConfigDict(extra="ignore")

    document_id: str
    title: str
    citation: str = ""
    court: str = ""
    date_decided: Optional[str] = None       # ISO date string
    binding_level: str = "informational"
    relevance_summary: str = ""
    top_chunk_citation_label: str = ""
    similarity_score: float = 0.0
    risk_flags: List[str] = Field(default_factory=list)
    tier: AuthorityTier = "strongest"
    distinguishing_reason: str = ""


class Excerpt(BaseModel):
    citation_label: str
    document_id: str
    chunk_id: str
    page_start: int
    page_end: int
    snippet: str


class ResearchAnswer(BaseModel):
    model_config = ConfigDict(extra="ignore")

    answer_id: str
    query_text: str
    query_type: str
    top_answer: str
    # Statutory provisions, constitutional articles, or doctrinal rules
    # drawn from the strongest precedents. One bullet per applicable item.
    applicable_law: List[str] = Field(default_factory=list)
    # Strongest authorities feed the answer; distinguishable ones are
    # listed so the lawyer knows what the engine considered and rejected.
    strongest_authorities: List[SupportingAuthority] = Field(default_factory=list)
    distinguishable_authorities: List[SupportingAuthority] = Field(default_factory=list)
    # Back-compat alias used by code that only wants the strongest set.
    # Populated automatically — do not set independently.
    authorities: List[SupportingAuthority] = Field(default_factory=list)
    excerpts: List[Excerpt] = Field(default_factory=list)
    risk_flags: List[str] = Field(default_factory=list)
    confidence: float = 0.0
    retrieval_summary: Dict[str, int] = Field(default_factory=dict)
    synthesis_source: SynthesisSource = "fallback"
    generated_at: datetime
    next_question: str = ""
    # Concrete next actions the lawyer should take based on this answer
    # (e.g., "Pull the trial-court record for X", "Check whether Y is still
    # good law after the 2023 amendment", "Brief the client on the binding
    # tier of authority").
    next_steps: List[str] = Field(default_factory=list)
