"""Strict Final Report schema — what gets persisted + exported."""
from __future__ import annotations

from datetime import datetime
from typing import List, Literal

from pydantic import BaseModel, ConfigDict, Field

from modules.evidence_vault.schemas.recommendation_schema import Recommendation
from modules.evidence_vault.schemas.scoring_schema import ScoreSet


Severity = Literal["low", "medium", "high", "critical"]


class SourceMapEntry(BaseModel):
    label: str
    document_id: str
    chunk_id: str = ""
    page_number: int = 1
    reason_used: str


class EvidencePoint(BaseModel):
    title: str
    snippet: str
    citation_label: str
    chunk_id: str = ""
    document_id: str = ""
    page: int = 1
    score: float = 0.0           # density / strength contribution


class ContradictionSummary(BaseModel):
    contradiction_id: str
    kind: str
    severity: Severity
    summary: str
    explanation: str
    references: List[str] = Field(default_factory=list)  # citation labels


class MissingEvidenceSummary(BaseModel):
    missing_id: str
    category: str
    severity: Severity
    why_it_matters: str
    recommendation: str


class IssueSummary(BaseModel):
    issue_name: str
    support_level: int                  # 0..100
    contradiction_impact: int           # 0..100 (higher = worse)
    missing_evidence_impact: int        # 0..100 (higher = worse)
    related_entities: List[str] = Field(default_factory=list)  # entity ids
    related_chunks:   List[str] = Field(default_factory=list)  # chunk ids
    legal_significance: str
    recommended_action: str


class FinalReport(BaseModel):
    model_config = ConfigDict(extra="ignore")

    report_id: str
    case_id: str
    generated_at: datetime

    scores: ScoreSet

    executive_summary: str
    strongest_issue: str
    weakest_issue: str

    strongest_points: List[EvidencePoint] = Field(default_factory=list)
    weakest_points:   List[EvidencePoint] = Field(default_factory=list)

    contradiction_summary:    List[ContradictionSummary]    = Field(default_factory=list)
    missing_evidence_summary: List[MissingEvidenceSummary]  = Field(default_factory=list)
    issue_matrix:             List[IssueSummary]            = Field(default_factory=list)
    recommendations:          List[Recommendation]          = Field(default_factory=list)

    final_conclusion: str = ""
    source_map: List[SourceMapEntry] = Field(default_factory=list)

    narrative_source: Literal["vertex", "aistudio", "fallback"] = "fallback"
