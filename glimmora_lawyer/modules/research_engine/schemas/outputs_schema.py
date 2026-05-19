"""Downstream payload — the public contract consumed by Packages 3/4/5.

This is intentionally the *only* schema a downstream package needs to import
from research_engine. Adding new fields here without removing/renaming old
ones is backward compatible by construction.
"""
from __future__ import annotations

from datetime import datetime
from typing import Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field

from modules.research_engine.schemas.answer_schema import SupportingAuthority


class TimelineItem(BaseModel):
    date: str                                    # ISO date or year — best-effort
    event: str
    source_document_id: str
    source_citation_label: str


class DownstreamPayload(BaseModel):
    model_config = ConfigDict(extra="ignore")

    case_id: str
    generated_at: datetime

    # Top authorities aggregated across the strongest sessions.
    top_authorities: List[SupportingAuthority] = Field(default_factory=list)

    # Dated events extracted from precedent bodies (best-effort).
    timeline_items: List[TimelineItem] = Field(default_factory=list)

    # Normalised case-strength signals in [0, 1].
    case_strength_signals: Dict[str, float] = Field(default_factory=dict)
    # Suggested keys:
    #   binding_support, persuasive_support, jurisdiction_coverage,
    #   recency_score, outcome_alignment, issue_coverage

    # Issue tags surfaced but not yet supported by any authority.
    unresolved_legal_issues: List[str] = Field(default_factory=list)

    # Bookkeeping so downstream packages can show provenance.
    session_count: int = 0
    corpus_doc_count: int = 0
    notes: Optional[str] = None
