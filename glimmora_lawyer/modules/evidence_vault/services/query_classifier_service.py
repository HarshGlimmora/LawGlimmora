"""Rule-based query intent classification + intent → (entity types, partitions) map.

Cheap and deterministic. The full retrieval pipeline can run hundreds of times
per session, so we avoid spending a Gemini call here.
"""
from __future__ import annotations

import re
from typing import Dict, List

from loguru import logger

from modules.evidence_vault.schemas.retrieval_schema import QueryIntent


INTENT_MAP: Dict[str, Dict[str, List[str]]] = {
    "timeline_query":                {"types": ["DATE", "EVENT"],
                                       "partitions": ["timeline"]},
    "party_query":                   {"types": ["PERSON", "ORG", "WITNESS"],
                                       "partitions": ["parties"]},
    "law_section_query":             {"types": ["SECTION", "ACT", "LAW", "RULE"],
                                       "partitions": ["legal_basis"]},
    "clause_query":                  {"types": ["CLAUSE"],
                                       "partitions": ["legal_basis"]},
    "evidence_query":                {"types": ["EVIDENCE_ITEM", "AMOUNT", "LOCATION"],
                                       "partitions": ["factual_evidence"]},
    "contradiction_reference_query": {"types": [], "partitions": []},
    "missing_evidence_query":        {"types": [], "partitions": []},
    "general_case_question":         {"types": [], "partitions": []},
    "entity_query":                  {"types": [], "partitions": []},
}


# Keyword patterns checked in priority order — first match wins.
_PATTERNS: List[tuple[str, re.Pattern]] = [
    ("contradiction_reference_query",
     re.compile(r"\b(contradict|inconsist|conflict|discrepan|contradiction)\w*", re.I)),
    ("missing_evidence_query",
     re.compile(r"\b(missing|absent|gap|lacking|not (?:in|present|filed|attached)|"
                r"what (?:is|are) (?:not|missing))\b", re.I)),
    ("timeline_query",
     re.compile(r"\b(date|dates|when|chronolog|timeline|sequence|hearing date|"
                r"filing date|incident date)\b", re.I)),
    ("party_query",
     re.compile(r"\b(party|parties|accused|complainant|petitioner|respondent|"
                r"plaintiff|defendant|witness|witnesses|client|advocate|"
                r"officer|guarantor)\b", re.I)),
    ("clause_query",
     re.compile(r"\b(clause|sub-?clause)\b", re.I)),
    ("law_section_query",
     re.compile(r"\b(section|act|law|rule|article|statute|provision)\b", re.I)),
    ("evidence_query",
     re.compile(r"\b(evidence|exhibit|annexure|amount|sum|consideration|"
                r"document|record|fir|police|statement|expert report)\b", re.I)),
    ("entity_query",
     re.compile(r"\b(entity|entities|extracted)\b", re.I)),
]


def classify(query: str) -> QueryIntent:
    """Returns the most specific intent that fires; defaults to general."""
    if not (query or "").strip():
        return "general_case_question"
    for intent, pat in _PATTERNS:
        if pat.search(query):
            logger.bind(scope="evidence.retrieval").info(
                "Query intent: {} | query={!r}", intent, query[:80],
            )
            return intent  # type: ignore[return-value]
    logger.bind(scope="evidence.retrieval").info(
        "Query intent: general_case_question | query={!r}", query[:80],
    )
    return "general_case_question"


def intent_filters(intent: str) -> Dict[str, List[str]]:
    return INTENT_MAP.get(intent, {"types": [], "partitions": []})
