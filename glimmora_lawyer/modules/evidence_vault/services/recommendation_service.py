"""Convert weaknesses (missing items, contradictions, weak issues) into a
prioritised, actionable plan."""
from __future__ import annotations

import uuid
from typing import List

from loguru import logger

from modules.evidence_vault.schemas.final_report_schema import IssueSummary
from modules.evidence_vault.schemas.recommendation_schema import (
    ActionType, Priority, Recommendation,
)

log = logger.bind(scope="evidence.recommendations")


def _new_id() -> str:
    return "rec-" + uuid.uuid4().hex[:10]


_SEV_TO_PRIORITY: dict[str, Priority] = {
    "critical": "critical", "high": "high",
    "medium": "medium",     "low": "low",
}


def _from_missing(items: List[dict]) -> List[Recommendation]:
    out: List[Recommendation] = []
    for m in items:
        sev = (m.get("severity") or "medium").lower()
        priority = _SEV_TO_PRIORITY.get(sev, "medium")
        out.append(Recommendation(
            recommendation_id=_new_id(),
            title=f"Supplement evidence — {m.get('category', 'gap')}",
            description=(m.get("recommendation")
                         or m.get("why_it_matters")
                         or "Upload supporting material to close this gap."),
            priority=priority,
            related_issue=m.get("category", ""),
            related_missing_ids=[m.get("id") or m.get("missing_id") or ""],
            action_type="upload",
        ))
    return out


def _from_contradictions(items: List[dict]) -> List[Recommendation]:
    out: List[Recommendation] = []
    for c in items:
        sev = (c.get("severity") or "medium").lower()
        priority = _SEV_TO_PRIORITY.get(sev, "medium")
        kind = c.get("kind", "")
        action: ActionType = "verify"
        if kind == "amount":
            action = "verify"
        elif kind == "date":
            action = "clarify"
        elif kind == "party_role":
            action = "review"
        out.append(Recommendation(
            recommendation_id=_new_id(),
            title=f"Resolve {kind} conflict",
            description=c.get("explanation") or c.get("summary") or "Verify conflicting references.",
            priority=priority,
            related_issue=c.get("summary", "")[:120],
            related_contradiction_ids=[c.get("id") or c.get("contradiction_id") or ""],
            action_type=action,
        ))
    return out


def _from_issue_matrix(matrix: List[IssueSummary]) -> List[Recommendation]:
    out: List[Recommendation] = []
    # Strengthen the two weakest issues that are not already covered by missing/contradiction recs.
    ranked = sorted(matrix, key=lambda i: i.support_level)
    for iss in ranked[:2]:
        if iss.support_level >= 60:
            continue
        priority: Priority = "high" if iss.support_level < 30 else "medium"
        out.append(Recommendation(
            recommendation_id=_new_id(),
            title=f"Strengthen issue: {iss.issue_name}",
            description=(f"Current support level {iss.support_level}/100. "
                         f"{iss.recommended_action}"),
            priority=priority,
            related_issue=iss.issue_name,
            related_chunk_ids=iss.related_chunks[:10],
            action_type="strengthen",
        ))
    # Highlight the strongest issue for "lead with this"
    if matrix:
        top = max(matrix, key=lambda i: i.support_level)
        if top.support_level >= 60:
            out.append(Recommendation(
                recommendation_id=_new_id(),
                title=f"Lead with: {top.issue_name}",
                description=(f"Strongest issue (support {top.support_level}/100). "
                             f"{top.legal_significance}"),
                priority="medium",
                related_issue=top.issue_name,
                related_chunk_ids=top.related_chunks[:10],
                action_type="summarize",
            ))
    return out


def _priority_rank(p: str) -> int:
    return {"critical": 0, "high": 1, "medium": 2, "low": 3}.get(p, 2)


def build_recommendations(
    *,
    missing_items: List[dict],
    contradictions: List[dict],
    issue_matrix: List[IssueSummary],
) -> List[Recommendation]:
    out: List[Recommendation] = []
    out.extend(_from_missing(missing_items))
    out.extend(_from_contradictions(contradictions))
    out.extend(_from_issue_matrix(issue_matrix))
    out.sort(key=lambda r: (_priority_rank(r.priority), r.title))
    log.info(
        "Recommendations: total={} (missing={} contradiction={} issue-based={})",
        len(out), len(missing_items), len(contradictions),
        len(out) - len(missing_items) - len(contradictions),
    )
    return out
