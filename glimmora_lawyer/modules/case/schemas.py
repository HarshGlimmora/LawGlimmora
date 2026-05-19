"""Pydantic schema for case creation/update."""
from __future__ import annotations

from datetime import date
from typing import Optional

from pydantic import BaseModel, Field, field_validator


class CaseIn(BaseModel):
    case_name: str = Field(min_length=3, max_length=200)
    case_type: str = Field(min_length=2, max_length=80)
    court_or_forum: str = Field(min_length=2, max_length=120)
    jurisdiction: str = Field(min_length=2, max_length=120)
    client_name: str = Field(min_length=2, max_length=160)
    party_names: str = Field(min_length=2, max_length=2000)
    your_role_in_case: str = Field(min_length=2, max_length=80)
    opposing_party_name: str = Field(min_length=2, max_length=255)
    filing_date: date
    next_hearing_date: Optional[date] = None
    urgency_level: str = Field(min_length=2, max_length=20)
    confidentiality_level: str = Field(min_length=2, max_length=20)
    case_status: str = Field(min_length=2, max_length=40)
    short_case_summary: str = Field(min_length=10, max_length=4000)
    internal_notes: Optional[str] = Field(default=None, max_length=8000)

    @field_validator("next_hearing_date")
    @classmethod
    def hearing_not_before_filing(cls, v: Optional[date], info) -> Optional[date]:
        filing = info.data.get("filing_date")
        if v and filing and v < filing:
            raise ValueError("Next hearing date cannot be before filing date")
        return v
