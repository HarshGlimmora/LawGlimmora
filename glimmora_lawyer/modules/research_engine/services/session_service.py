"""Research-session persistence: one JSON per query/answer round trip.

A session captures everything needed to reproduce the answer later — the
query, the ranked hits, the synthesised answer, the user's notes — so
downstream packages can audit *why* an authority surfaced in the report.
"""
from __future__ import annotations

import uuid
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from loguru import logger

from modules.research_engine.schemas.answer_schema import ResearchAnswer
from modules.research_engine.schemas.retrieval_schema import (
    RankedHit, ResearchQuery,
)
from modules.research_engine.schemas.session_schema import ResearchSession
from modules.research_engine.services.persistence_service import (
    ensure_case_dirs, session_path, sessions_dir,
)


log = logger.bind(scope="research.session")


def new_session_id() -> str:
    return "sess-" + uuid.uuid4().hex[:12]


def build_session(
    case_id: int | str,
    query: ResearchQuery,
    answer: ResearchAnswer,
    ranked_hits: List[RankedHit],
    user_notes: str = "",
    pinned_document_ids: List[str] | None = None,
    unresolved_questions: List[str] | None = None,
) -> ResearchSession:
    return ResearchSession(
        session_id=new_session_id(),
        case_id=str(case_id),
        query_text=query.query_text,
        query_type=query.query_type,
        created_at=datetime.utcnow(),
        answer=answer,
        ranked_hits=ranked_hits,
        user_notes=user_notes,
        pinned_document_ids=list(pinned_document_ids or []),
        unresolved_questions=list(unresolved_questions or []),
    )


def update_session_feedback(
    case_id: int | str,
    session_id: str,
    *,
    pinned_document_ids: List[str] | None = None,
    user_feedback: str | None = None,
    unresolved_questions: List[str] | None = None,
    user_notes: str | None = None,
) -> Optional[ResearchSession]:
    """In-place update of a session's feedback fields. Returns the new
    session (or None if it does not exist). Pass `None` for any field you
    want left untouched."""
    sess = load_session(case_id, session_id)
    if not sess:
        return None
    if pinned_document_ids is not None:
        sess.pinned_document_ids = list(pinned_document_ids)
    if user_feedback is not None:
        if user_feedback not in ("thumbs_up", "thumbs_down", "neutral"):
            raise ValueError(
                f"Invalid user_feedback {user_feedback!r}; must be one of "
                "thumbs_up | thumbs_down | neutral.",
            )
        sess.user_feedback = user_feedback  # type: ignore[assignment]
    if unresolved_questions is not None:
        sess.unresolved_questions = list(unresolved_questions)
    if user_notes is not None:
        sess.user_notes = user_notes
    save_session(case_id, sess)
    return sess


def save_session(case_id: int | str, session: ResearchSession) -> Path:
    ensure_case_dirs(case_id)
    p = session_path(case_id, session.session_id)
    p.write_text(session.model_dump_json(indent=2), encoding="utf-8")
    log.info("Saved research session: {}", p)
    return p


def load_session(case_id: int | str, session_id: str) -> Optional[ResearchSession]:
    p = session_path(case_id, session_id)
    if not p.exists():
        return None
    return ResearchSession.model_validate_json(p.read_text(encoding="utf-8"))


def list_sessions(case_id: int | str) -> List[ResearchSession]:
    folder = sessions_dir(case_id)
    if not folder.exists():
        return []
    out: List[ResearchSession] = []
    for p in sorted(folder.glob("*.json"), key=lambda p: p.stat().st_mtime,
                    reverse=True):
        try:
            out.append(ResearchSession.model_validate_json(
                p.read_text(encoding="utf-8")
            ))
        except Exception as exc:
            log.warning("Skipping unparseable session file {}: {}", p, exc)
    return out
