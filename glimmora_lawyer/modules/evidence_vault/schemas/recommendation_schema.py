"""Recommendation schema — actionable next steps tied to weaknesses."""
from __future__ import annotations

from typing import List, Literal

from pydantic import BaseModel, ConfigDict, Field


Priority = Literal["low", "medium", "high", "critical"]
ActionType = Literal[
    "upload", "verify", "clarify", "strengthen", "review", "summarize",
]


class Recommendation(BaseModel):
    model_config = ConfigDict(extra="ignore")

    recommendation_id: str
    title: str
    description: str
    priority: Priority = "medium"
    related_issue: str = ""
    related_contradiction_ids: List[str] = Field(default_factory=list)
    related_missing_ids:       List[str] = Field(default_factory=list)
    related_chunk_ids:         List[str] = Field(default_factory=list)
    action_type: ActionType = "review"


class RecommendationPlan(BaseModel):
    case_id: str
    items: List[Recommendation] = Field(default_factory=list)
