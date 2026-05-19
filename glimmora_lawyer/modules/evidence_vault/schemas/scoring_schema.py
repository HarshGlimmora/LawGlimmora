"""Scoring schema — 9 normalized scores + explainability breakdowns."""
from __future__ import annotations

from datetime import datetime
from typing import List, Literal

from pydantic import BaseModel, ConfigDict, Field


Direction = Literal["higher_better", "lower_better"]


# The 9 scores (0..100) emitted to the final report. Field names match the
# canonical JSON exactly.
class ScoreSet(BaseModel):
    model_config = ConfigDict(extra="ignore")

    evidence_strength_score:      int = Field(ge=0, le=100, default=0)
    evidence_weakness_score:      int = Field(ge=0, le=100, default=0)
    completeness_score:           int = Field(ge=0, le=100, default=0)
    contradiction_risk_score:     int = Field(ge=0, le=100, default=0)
    missing_evidence_risk_score:  int = Field(ge=0, le=100, default=0)
    timeline_integrity_score:     int = Field(ge=0, le=100, default=0)
    legal_basis_strength_score:   int = Field(ge=0, le=100, default=0)
    readiness_score:              int = Field(ge=0, le=100, default=0)
    pitch_success_estimate:       int = Field(ge=0, le=100, default=0)


class ScoreFactor(BaseModel):
    name: str
    contribution: float          # signed delta in score points (raw, pre-clamp)
    explanation: str


class ScoreBreakdown(BaseModel):
    score_name: str
    value: int
    direction: Direction
    explanation: str
    factors: List[ScoreFactor] = Field(default_factory=list)


class ScoreSummary(BaseModel):
    case_id: str
    generated_at: datetime
    scores: ScoreSet
    breakdowns: List[ScoreBreakdown] = Field(default_factory=list)
