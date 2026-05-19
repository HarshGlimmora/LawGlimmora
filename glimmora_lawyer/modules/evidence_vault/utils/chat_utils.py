"""Chat history serialisation helpers."""
from __future__ import annotations

import uuid
from datetime import datetime

from modules.evidence_vault.schemas.chat_schema import ChatTurn


def new_turn_id() -> str:
    return "trn-" + uuid.uuid4().hex[:12]


def make_user_turn(message: str) -> ChatTurn:
    return ChatTurn(
        turn_id=new_turn_id(), role="user", ts=datetime.utcnow(),
        message=message,
    )


def make_assistant_turn(message: str, *, answer_id: str, intent: str,
                        citations: list[dict]) -> ChatTurn:
    return ChatTurn(
        turn_id=new_turn_id(), role="assistant", ts=datetime.utcnow(),
        message=message, answer_id=answer_id, intent=intent,
        citations=citations,
    )
