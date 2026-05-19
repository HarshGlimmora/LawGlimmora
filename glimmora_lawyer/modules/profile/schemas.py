"""Pydantic schema for profile creation/update."""
from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, EmailStr, Field, field_validator


class ProfileIn(BaseModel):
    full_name: str = Field(min_length=2, max_length=160)
    display_name: str = Field(min_length=1, max_length=80)
    email: EmailStr
    firm_name: str = Field(min_length=2, max_length=160)
    practice_area: str = Field(min_length=2, max_length=80)
    years_of_experience: int = Field(ge=0, le=70)
    jurisdiction_focus: str = Field(min_length=2, max_length=120)
    city: str = Field(min_length=2, max_length=80)
    preferred_languages: List[str] = Field(min_length=1)
    bar_registration_id: Optional[str] = Field(default=None, max_length=80)
    phone: Optional[str] = Field(default=None, max_length=40)
    default_workspace_theme: str = Field(min_length=2, max_length=40)

    @field_validator("preferred_languages")
    @classmethod
    def non_empty_languages(cls, v: List[str]) -> List[str]:
        cleaned = [x.strip() for x in v if x and x.strip()]
        if not cleaned:
            raise ValueError("Select at least one preferred language")
        return cleaned
