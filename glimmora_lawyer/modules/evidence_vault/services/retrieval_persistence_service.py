"""On-disk persistence for the retrieval + chat surfaces.

Paths:
  cases/<case_id>/evidence/retrieval/
    retrieval_index.json
    entity_search_cache.json
    retrieval_debug.json
  cases/<case_id>/evidence/chat/
    chat_history.json
    chat_responses.json
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from loguru import logger

from modules.evidence_vault.schemas.answer_schema import Answer
from modules.evidence_vault.schemas.chat_schema import ChatHistory, ChatTurn
from modules.evidence_vault.schemas.retrieval_schema import RetrievalContext
from modules.evidence_vault.services.persistence_service import (
    case_evidence_root, ensure_case_dirs,
)


def _retrieval_dir(case_id: int | str) -> Path:
    p = case_evidence_root(case_id) / "retrieval"
    p.mkdir(parents=True, exist_ok=True)
    return p


def _chat_dir(case_id: int | str) -> Path:
    p = case_evidence_root(case_id) / "chat"
    p.mkdir(parents=True, exist_ok=True)
    return p


# ---- retrieval_index.json --------------------------------------------------

def write_retrieval_index(case_id: int | str, *,
                          chunks_summary: List[dict],
                          entities_summary: List[dict],
                          partitions_summary: Dict[str, int]) -> Path:
    ensure_case_dirs(case_id)
    payload = {
        "case_id": str(case_id),
        "generated_at": datetime.utcnow().isoformat(timespec="seconds"),
        "total_chunks": len(chunks_summary),
        "total_entities": len(entities_summary),
        "partitions": partitions_summary,
        "chunks_summary": chunks_summary,
        "entities_summary": entities_summary,
    }
    p = _retrieval_dir(case_id) / "retrieval_index.json"
    p.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    logger.bind(scope="evidence.retrieval").info(
        "Wrote retrieval_index.json (chunks={}, entities={})",
        len(chunks_summary), len(entities_summary),
    )
    return p


def load_retrieval_index(case_id: int | str) -> Optional[dict]:
    p = _retrieval_dir(case_id) / "retrieval_index.json"
    if not p.exists():
        return None
    return json.loads(p.read_text(encoding="utf-8"))


# ---- entity_search_cache.json (latest queries + their entity hits) ---------

MAX_CACHE_ENTRIES = 20


def append_search_cache(case_id: int | str, *, query: str, intent: str,
                        entity_hits: List[dict]) -> None:
    p = _retrieval_dir(case_id) / "entity_search_cache.json"
    items: List[dict] = []
    if p.exists():
        try:
            items = json.loads(p.read_text(encoding="utf-8")).get("queries", [])
        except Exception:
            items = []
    items.insert(0, {
        "ts": datetime.utcnow().isoformat(timespec="seconds"),
        "query": query, "intent": intent,
        "entity_hits": entity_hits[:20],
    })
    items = items[:MAX_CACHE_ENTRIES]
    p.write_text(json.dumps({"queries": items}, indent=2), encoding="utf-8")


def load_search_cache(case_id: int | str) -> List[dict]:
    p = _retrieval_dir(case_id) / "entity_search_cache.json"
    if not p.exists():
        return []
    try:
        return json.loads(p.read_text(encoding="utf-8")).get("queries", [])
    except Exception:
        return []


# ---- retrieval_debug.json (latest retrieval payload) -----------------------

def write_retrieval_debug(case_id: int | str, ctx: RetrievalContext) -> Path:
    p = _retrieval_dir(case_id) / "retrieval_debug.json"
    p.write_text(ctx.model_dump_json(indent=2), encoding="utf-8")
    return p


def load_retrieval_debug(case_id: int | str) -> Optional[dict]:
    p = _retrieval_dir(case_id) / "retrieval_debug.json"
    if not p.exists():
        return None
    return json.loads(p.read_text(encoding="utf-8"))


# ---- chat_history.json -----------------------------------------------------

def load_chat_history(case_id: int | str) -> ChatHistory:
    p = _chat_dir(case_id) / "chat_history.json"
    if not p.exists():
        return ChatHistory(case_id=str(case_id))
    try:
        return ChatHistory.model_validate_json(p.read_text(encoding="utf-8"))
    except Exception:
        return ChatHistory(case_id=str(case_id))


def append_chat_turn(case_id: int | str, turn: ChatTurn) -> None:
    history = load_chat_history(case_id)
    history.turns.append(turn)
    p = _chat_dir(case_id) / "chat_history.json"
    p.write_text(history.model_dump_json(indent=2), encoding="utf-8")


def clear_chat_history(case_id: int | str) -> None:
    p = _chat_dir(case_id) / "chat_history.json"
    if p.exists():
        p.unlink()


# ---- chat_responses.json (full Answer objects per assistant turn) ---------

def append_answer(case_id: int | str, answer: Answer) -> None:
    p = _chat_dir(case_id) / "chat_responses.json"
    items: List[dict] = []
    if p.exists():
        try:
            items = json.loads(p.read_text(encoding="utf-8")).get("answers", [])
        except Exception:
            items = []
    items.append(answer.model_dump(mode="json"))
    p.write_text(json.dumps({"answers": items}, indent=2,
                            default=str), encoding="utf-8")


def load_answers(case_id: int | str) -> List[dict]:
    p = _chat_dir(case_id) / "chat_responses.json"
    if not p.exists():
        return []
    try:
        return json.loads(p.read_text(encoding="utf-8")).get("answers", [])
    except Exception:
        return []
