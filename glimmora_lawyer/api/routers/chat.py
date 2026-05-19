"""Evidence chat routes."""
from __future__ import annotations

from fastapi import APIRouter, Depends

from api.deps import require_profile
from api.errors import DomainError
from modules.case.services.case_service import get_case
from modules.evidence_vault.services.evidence_chat_service import ask
from modules.evidence_vault.services.retrieval_persistence_service import (
    clear_chat_history, load_chat_history,
)

router = APIRouter(prefix="/api/cases/{case_id}/evidence/chat", tags=["chat"])


def _ensure_case(case_id: int, uid: int) -> None:
    if not get_case(uid, case_id):
        raise DomainError("case_not_found", "Case not found.", status_code=404)


@router.get("")
def get_chat(case_id: int, uid: int = Depends(require_profile)) -> dict:
    _ensure_case(case_id, uid)
    return load_chat_history(case_id).model_dump(mode="json")


@router.post("")
def post_chat(case_id: int, body: dict, uid: int = Depends(require_profile)) -> dict:
    _ensure_case(case_id, uid)
    query = (body.get("query") or "").strip()
    if not query:
        raise DomainError("empty_query", "Query is empty.", status_code=400)
    mode = body.get("mode") or "hybrid"
    partition_filter = body.get("partition_filter")
    answer, ctx = ask(case_id=case_id, query=query, mode=mode,
                      partition_filter=partition_filter)
    return {
        "answer": answer.model_dump(mode="json"),
        "context": ctx.model_dump(mode="json"),
    }


@router.delete("")
def delete_chat(case_id: int, uid: int = Depends(require_profile)) -> dict:
    _ensure_case(case_id, uid)
    clear_chat_history(case_id)
    return {"ok": True}
