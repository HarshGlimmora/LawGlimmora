"""Case routes."""
from __future__ import annotations

from typing import List

from fastapi import APIRouter, Depends

from api.deps import require_profile
from api.errors import DomainError
from modules.case.schemas import CaseIn
from modules.case.services.case_service import (
    CaseError, create_case, get_case, list_cases, update_case,
)

router = APIRouter(prefix="/api/cases", tags=["cases"])


@router.get("", response_model=List[dict])
def list_my_cases(uid: int = Depends(require_profile)) -> List[dict]:
    return list_cases(uid)


@router.post("", response_model=dict)
def create_my_case(data: CaseIn, uid: int = Depends(require_profile)) -> dict:
    try:
        return create_case(uid, data)
    except CaseError as e:
        raise DomainError("case_create_failed", str(e), status_code=400)


@router.get("/{case_id}", response_model=dict)
def get_my_case(case_id: int, uid: int = Depends(require_profile)) -> dict:
    case = get_case(uid, case_id)
    if not case:
        raise DomainError("case_not_found", "Case not found.", status_code=404)
    return case


@router.put("/{case_id}", response_model=dict)
def update_my_case(case_id: int, data: CaseIn,
                   uid: int = Depends(require_profile)) -> dict:
    try:
        return update_case(uid, case_id, data)
    except CaseError as e:
        raise DomainError("case_update_failed", str(e), status_code=400)
