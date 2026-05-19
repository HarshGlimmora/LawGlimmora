"""Profile routes."""
from __future__ import annotations

from fastapi import APIRouter, Depends

from api.deps import current_user_id
from api.errors import DomainError
from modules.profile.schemas import ProfileIn
from modules.profile.services.profile_service import (
    ProfileError, get_profile, upsert_profile,
)

router = APIRouter(prefix="/api/profile", tags=["profile"])


@router.get("")
def get_my_profile(uid: int = Depends(current_user_id)) -> dict:
    prof = get_profile(uid)
    return prof or {}


@router.put("")
def put_my_profile(data: ProfileIn, uid: int = Depends(current_user_id)) -> dict:
    try:
        return upsert_profile(uid, data)
    except ProfileError as e:
        raise DomainError("profile_save_failed", str(e), status_code=400)
