"""Case service: list / create / fetch / update."""
from __future__ import annotations

from typing import List, Optional

from core.db import Case, session_scope, write_audit
from core.logging import get_logger
from modules.case.schemas import CaseIn

log = get_logger("case.service")


class CaseError(Exception):
    pass


def _to_dict(c: Case) -> dict:
    return {
        "id": c.id, "user_id": c.user_id, "case_name": c.case_name,
        "case_type": c.case_type, "court_or_forum": c.court_or_forum,
        "jurisdiction": c.jurisdiction, "client_name": c.client_name,
        "party_names": c.party_names, "your_role_in_case": c.your_role_in_case,
        "opposing_party_name": c.opposing_party_name,
        "filing_date": c.filing_date, "next_hearing_date": c.next_hearing_date,
        "urgency_level": c.urgency_level,
        "confidentiality_level": c.confidentiality_level,
        "case_status": c.case_status,
        "short_case_summary": c.short_case_summary, "internal_notes": c.internal_notes,
        "created_at": c.created_at, "updated_at": c.updated_at,
    }


def list_cases(user_id: int) -> List[dict]:
    with session_scope() as sess:
        rows = (
            sess.query(Case)
            .filter(Case.user_id == user_id)
            .order_by(Case.updated_at.desc())
            .all()
        )
        return [_to_dict(c) for c in rows]


def get_case(user_id: int, case_id: int) -> Optional[dict]:
    with session_scope() as sess:
        c = sess.query(Case).filter(Case.user_id == user_id, Case.id == case_id).one_or_none()
        return _to_dict(c) if c else None


def create_case(user_id: int, data: CaseIn) -> dict:
    with session_scope() as sess:
        c = Case(user_id=user_id, **data.model_dump())
        sess.add(c)
        sess.flush()
        write_audit(sess, user_id=user_id, action="case.create", target_type="case", target_id=c.id,
                    message=c.case_name)
        log.info("Case created: user_id={} case_id={} name={!r}", user_id, c.id, c.case_name)
        return _to_dict(c)


def update_case(user_id: int, case_id: int, data: CaseIn) -> dict:
    with session_scope() as sess:
        c = sess.query(Case).filter(Case.user_id == user_id, Case.id == case_id).one_or_none()
        if not c:
            raise CaseError("Case not found.")
        for k, v in data.model_dump().items():
            setattr(c, k, v)
        sess.flush()
        write_audit(sess, user_id=user_id, action="case.update", target_type="case", target_id=c.id,
                    message=c.case_name)
        log.info("Case updated: user_id={} case_id={}", user_id, c.id)
        return _to_dict(c)
