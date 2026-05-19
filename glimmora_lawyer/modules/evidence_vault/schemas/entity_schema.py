"""Entity + partition schemas."""
from __future__ import annotations

from typing import List, Literal

from pydantic import BaseModel, ConfigDict, Field


EntityType = Literal[
    "PERSON", "ORG", "COURT", "CASE_NUMBER", "LAW", "ACT", "SECTION",
    "RULE", "CLAUSE", "DATE", "EVENT", "LOCATION", "AMOUNT",
    "EVIDENCE_ITEM", "WITNESS", "POLICE_STATION", "FIR_NUMBER",
    "ORDER_NUMBER",
]


ENTITY_TYPES: List[str] = [
    "PERSON", "ORG", "COURT", "CASE_NUMBER", "LAW", "ACT", "SECTION",
    "RULE", "CLAUSE", "DATE", "EVENT", "LOCATION", "AMOUNT",
    "EVIDENCE_ITEM", "WITNESS", "POLICE_STATION", "FIR_NUMBER",
    "ORDER_NUMBER",
]


PartitionType = Literal[
    "parties", "timeline", "legal_basis", "factual_evidence", "procedural_facts",
]


PARTITION_TYPES: List[str] = [
    "parties", "timeline", "legal_basis", "factual_evidence", "procedural_facts",
]


# Which legal-meaning partition each entity type belongs to.
PARTITION_FOR_TYPE: dict[str, str] = {
    # parties
    "PERSON": "parties",
    "ORG": "parties",
    "WITNESS": "parties",
    # timeline
    "DATE": "timeline",
    "EVENT": "timeline",
    # legal_basis
    "ACT": "legal_basis",
    "LAW": "legal_basis",
    "SECTION": "legal_basis",
    "RULE": "legal_basis",
    "CLAUSE": "legal_basis",
    # factual_evidence
    "EVIDENCE_ITEM": "factual_evidence",
    "AMOUNT": "factual_evidence",
    "LOCATION": "factual_evidence",
    # procedural_facts
    "COURT": "procedural_facts",
    "CASE_NUMBER": "procedural_facts",
    "ORDER_NUMBER": "procedural_facts",
    "FIR_NUMBER": "procedural_facts",
    "POLICE_STATION": "procedural_facts",
}


class EntityRecord(BaseModel):
    model_config = ConfigDict(extra="ignore")

    entity_id: str
    entity_type: EntityType
    value: str
    normalized_value: str
    source_chunk_id: str
    source_document_id: str
    source_page: int = Field(ge=1)
    context_excerpt: str = ""
    confidence: float = 0.95


class Partition(BaseModel):
    partition_type: PartitionType
    entities: List[EntityRecord] = Field(default_factory=list)


# ---- Gemini structured-output schema (per chunk) ----

class GeminiEntity(BaseModel):
    """Shape Gemini returns for one entity. Source metadata is filled in
    by the orchestrator after parsing."""
    entity_type: EntityType
    value: str
    normalized_value: str = ""
    context_excerpt: str = ""
    confidence: float = 0.9


class GeminiEntityList(BaseModel):
    entities: List[GeminiEntity] = Field(default_factory=list)
