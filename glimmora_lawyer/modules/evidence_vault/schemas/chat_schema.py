"""Chat history schema."""
from __future__ import annotations

from datetime import datetime
from typing import List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


Role = Literal["user", "assistant"]


class ChatTurn(BaseModel):
    model_config = ConfigDict(extra="ignore")

    turn_id: str
    role: Role
    ts: datetime
    message: str
    answer_id: Optional[str] = None    # links assistant turns back to chat_responses.json
    intent: Optional[str] = None        # only set for assistant turns
    citations: List[dict] = Field(default_factory=list)


class ChatHistory(BaseModel):
    case_id: str
    turns: List[ChatTurn] = Field(default_factory=list)
