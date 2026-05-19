"""Read-only constants the frontend needs for dropdowns."""
from __future__ import annotations

from fastapi import APIRouter

from config import constants as C
from modules.evidence_vault.schemas.evidence_schema import EVIDENCE_DOC_TYPES
from modules.evidence_vault.schemas.retrieval_schema import SUGGESTED_PROMPTS

router = APIRouter(prefix="/api/constants", tags=["constants"])


@router.get("")
def get_constants() -> dict:
    return {
        "practice_areas": C.PRACTICE_AREAS,
        "indian_jurisdictions": C.INDIAN_JURISDICTIONS,
        "languages": C.LANGUAGES,
        "case_types": C.CASE_TYPES,
        "roles_in_case": C.ROLES_IN_CASE,
        "urgency_levels": C.URGENCY_LEVELS,
        "confidentiality_levels": C.CONFIDENTIALITY_LEVELS,
        "case_statuses": C.CASE_STATUSES,
        "workspace_themes": C.WORKSPACE_THEMES,
        "evidence_doc_types": EVIDENCE_DOC_TYPES,
        "suggested_prompts": SUGGESTED_PROMPTS,
    }
