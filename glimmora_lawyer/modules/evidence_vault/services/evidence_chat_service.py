"""Public entry point for the Evidence Chat tab.

`ask(...)` runs the full pipeline:
  1. retrieve(query) → RetrievalContext
  2. synthesize(ctx)  → Answer
  3. persist user turn, assistant turn, answer, debug
"""
from __future__ import annotations

from typing import List, Optional

from loguru import logger

from modules.evidence_vault.schemas.answer_schema import Answer
from modules.evidence_vault.schemas.retrieval_schema import (
    RetrievalContext, RetrievalMode,
)
from modules.evidence_vault.services.answer_synthesis_service import synthesize
from modules.evidence_vault.services.retrieval_persistence_service import (
    append_answer, append_chat_turn,
)
from modules.evidence_vault.services.retrieval_service import retrieve
from modules.evidence_vault.utils.chat_utils import (
    make_assistant_turn, make_user_turn,
)


def ask(
    *,
    case_id: int | str,
    query: str,
    mode: RetrievalMode = "hybrid",
    partition_filter: Optional[List[str]] = None,
) -> tuple[Answer, RetrievalContext]:
    bound = logger.bind(scope="evidence.chat")
    bound.info("Ask: case={} mode={} partitions={} query={!r}",
               case_id, mode, partition_filter or "-", (query or "")[:120])

    user_turn = make_user_turn(query)
    append_chat_turn(case_id, user_turn)

    ctx = retrieve(case_id=case_id, query=query, mode=mode,
                   partition_filter=partition_filter)
    answer = synthesize(ctx)

    citations = [
        {"citation_label": s.citation_label, "page": s.page,
         "chunk_id": s.chunk_id, "document_id": s.document_id}
        for s in answer.supporting_sources
    ]
    assistant_turn = make_assistant_turn(
        message=answer.final_answer,
        answer_id=answer.answer_id, intent=answer.intent,
        citations=citations,
    )
    append_chat_turn(case_id, assistant_turn)
    append_answer(case_id, answer)

    bound.info(
        "Answered: intent={} sources={} conf={:.2f} synthesis={} warnings={}",
        answer.intent, len(answer.supporting_sources),
        answer.confidence, answer.synthesis_source, len(answer.warnings),
    )
    return answer, ctx
