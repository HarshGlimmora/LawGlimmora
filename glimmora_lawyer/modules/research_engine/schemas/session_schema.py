"""Research session — the persisted memory unit."""
from __future__ import annotations

from datetime import datetime
from typing import List, Literal

from pydantic import BaseModel, ConfigDict, Field

from modules.research_engine.schemas.answer_schema import ResearchAnswer
from modules.research_engine.schemas.retrieval_schema import RankedHit


UserFeedback = Literal["thumbs_up", "thumbs_down", "neutral"]


class ResearchSession(BaseModel):
    """Persisted research memory unit.

    The feedback fields are mutated *after* save via the PATCH endpoint:
    the lawyer rates the answer, pins useful precedents, and writes down
    questions the engine could not resolve. Those signals feed the
    DownstreamPayload aggregator so weak corners of the corpus surface in
    later packages.
    """
    model_config = ConfigDict(extra="ignore")

    session_id: str
    case_id: str
    query_text: str
    query_type: str
    created_at: datetime
    answer: ResearchAnswer
    ranked_hits: List[RankedHit] = Field(default_factory=list)
    user_notes: str = ""
    # Feedback fields — mutable after initial save.
    pinned_document_ids: List[str] = Field(default_factory=list)
    user_feedback: UserFeedback = "neutral"
    unresolved_questions: List[str] = Field(default_factory=list)
