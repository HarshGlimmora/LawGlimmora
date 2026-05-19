"""Canonical schemas for the research corpus.

A PrecedentDocument is the on-disk shape per ingested precedent PDF.
Metadata starts empty and is populated by metadata_service after extraction.
"""
from __future__ import annotations

from datetime import date, datetime
from typing import List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


BindingLevel = Literal["binding", "persuasive", "informational"]
IngestionStatus = Literal["pending", "extracted", "enriched", "indexed", "failed"]
SourceType = Literal["pdf_upload", "plain_text", "seeded_corpus", "api"]


class PrecedentPage(BaseModel):
    page_number: int = Field(ge=1)
    text: str = ""


class PrecedentMeta(BaseModel):
    """Structured metadata extracted from the precedent body.

    Empty string / empty list defaults mean "not yet extracted" — callers
    inspect them rather than treating missing as null.
    """
    model_config = ConfigDict(extra="ignore")

    document_id: str
    title: str = ""
    citation: str = ""
    court: str = ""
    judges: List[str] = Field(default_factory=list)
    date_decided: Optional[date] = None
    jurisdiction: str = "India"
    practice_areas: List[str] = Field(default_factory=list)
    issue_tags: List[str] = Field(default_factory=list)
    outcome: Optional[str] = None
    binding_level: BindingLevel = "informational"
    headnote: Optional[str] = None
    ratio: Optional[str] = None
    # Provenance + trust signals — populated during enrichment.
    source_type: SourceType = "pdf_upload"
    source_reference: str = ""                # filename, URL, reporter, or hash
    confidence_score: float = Field(default=0.0, ge=0.0, le=1.0)


class PrecedentDocument(BaseModel):
    """Top-level payload persisted to disk per precedent."""
    model_config = ConfigDict(extra="ignore")

    document_id: str
    case_id: str
    filename: str
    ingested_at: datetime
    page_count: int = 0
    full_text: str = ""
    pages: List[PrecedentPage] = Field(default_factory=list)
    meta: PrecedentMeta
    status: IngestionStatus = "pending"
    chunks_built: bool = False
    indexed: bool = False
    notes: Optional[str] = None


# ---- ingestion log ----

LogStatus = Literal["ok", "skipped", "error"]


class IngestionLogStep(BaseModel):
    name: str
    status: LogStatus
    at: datetime
    detail: Optional[str] = None


class IngestionLog(BaseModel):
    document_id: str
    case_id: str
    filename: str
    started_at: datetime
    ended_at: Optional[datetime] = None
    duration_ms: int = 0
    result: Literal["completed", "failed"] = "completed"
    steps: List[IngestionLogStep] = Field(default_factory=list)
    error: Optional[str] = None
