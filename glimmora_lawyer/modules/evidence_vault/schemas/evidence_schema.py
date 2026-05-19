"""Canonical evidence schema.

Authoritative on-disk shape for one ingested evidence document.
Empty arrays at the top level are intentional — downstream packages
(chunks/entities/claims/contradictions/missing/argument recs) populate
them in place without changing the schema.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


ProcessingStatus = Literal["pending", "extracting", "completed", "failed"]
EvidenceSource = Literal["user_upload", "ingested", "api"]


EVIDENCE_DOC_TYPES: List[str] = [
    "FIR",
    "Complaint",
    "Petition",
    "Witness Statement",
    "Legal Notice",
    "Agreement",
    "Court Order",
    "Annexure",
    "Other",
]


class CitationAnchor(BaseModel):
    citation_id: str
    document_id: str
    filename: str
    page_number: int = Field(ge=1)
    citation_label: str


class PageRecord(BaseModel):
    page_number: int = Field(ge=1)
    raw_text: str = ""
    clean_text: str = ""
    page_hash: str = ""
    character_count: int = 0
    word_count: int = 0
    citations: List[CitationAnchor] = Field(default_factory=list)
    entities: List[Dict[str, Any]] = Field(default_factory=list)
    claims: List[Dict[str, Any]] = Field(default_factory=list)


class DocumentMeta(BaseModel):
    model_config = ConfigDict(extra="ignore")

    document_id: str
    case_id: str
    filename: str
    evidence_title: str
    doc_type: str
    source: EvidenceSource = "user_upload"
    language: str = "en"
    jurisdiction: str = "India"
    uploaded_at: datetime
    page_count: int = 0
    processing_status: ProcessingStatus = "pending"
    notes: Optional[str] = None


class ExtractionSummary(BaseModel):
    total_pages: int = 0
    total_characters: int = 0
    total_words: int = 0
    extraction_duration_ms: int = 0


class CanonicalEvidence(BaseModel):
    """The top-level shape persisted to disk per document."""
    document: DocumentMeta
    pages: List[PageRecord] = Field(default_factory=list)
    chunks: List[Dict[str, Any]] = Field(default_factory=list)
    entities: List[Dict[str, Any]] = Field(default_factory=list)
    claims: List[Dict[str, Any]] = Field(default_factory=list)
    contradictions: List[Dict[str, Any]] = Field(default_factory=list)
    missing_evidence: List[Dict[str, Any]] = Field(default_factory=list)
    argument_recommendations: List[Dict[str, Any]] = Field(default_factory=list)
    summary: ExtractionSummary = Field(default_factory=ExtractionSummary)


# ---- per-document extraction log ----

LogStepStatus = Literal["ok", "skipped", "error"]


class LogStep(BaseModel):
    name: str
    status: LogStepStatus
    at: datetime
    detail: Optional[str] = None


class ExtractionLog(BaseModel):
    document_id: str
    case_id: str
    filename: str
    started_at: datetime
    ended_at: Optional[datetime] = None
    duration_ms: int = 0
    page_count: int = 0
    result: Literal["completed", "failed"] = "completed"
    steps: List[LogStep] = Field(default_factory=list)
    error: Optional[str] = None
