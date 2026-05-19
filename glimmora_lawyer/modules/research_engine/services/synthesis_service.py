"""Take the reranked hits and produce a ResearchAnswer.

Primary: Vertex AI Gemini with a strict response schema. The prompt
explicitly bounds citations to a whitelist drawn from the reranked set, so
the model cannot fabricate authority labels. We post-process the prose to
recover any allowed citations the model wrote inline but forgot to list in
the structured field, then warn if the prose names citations that we
couldn't ground.

Fallback: a deterministic template that quotes the top-ranked excerpts
and lists the top three authorities. Used when Gemini is unavailable or
returns an unparseable response.

The flow lives behind one public function: `synthesize(case_id, query,
ranked)`. The orchestrator (page) calls retrieval → rerank → synthesize
and never branches.
"""
from __future__ import annotations

import json as _json
import re
import uuid
from datetime import datetime
from typing import Dict, List

from loguru import logger

from modules.research_engine.schemas.answer_schema import (
    Excerpt, ResearchAnswer, SupportingAuthority,
)
from modules.research_engine.schemas.retrieval_schema import (
    RankedHit, ResearchQuery,
)
from modules.evidence_vault.services.ai_extractor import (
    gemini_model, get_gemini_client, looks_like_auth_error,
    mark_vertex_failed,
)


log = logger.bind(scope="research.synthesis")


# ---------- Prompt + schema ----------

_PROMPT = """You are Glimmora Lawyer's research engine. Answer the user's
legal-research query strictly from the precedent excerpts below — never
from prior knowledge. Indian-law context.

HARD RULES:
  * Never invent case names, citations, courts, dates, paragraph numbers,
    or holdings. Quote only what the excerpts contain.
  * Every citation you write must be EXACTLY one of the labels in ALLOWED
    CITATIONS. Labels outside that list will be discarded.
  * If excerpts are weak, contradictory, or silent on the question, say so
    plainly and add a risk_flag.
  * Tone: concise, neutral, legal-professional. Maximum 8 sentences in
    top_answer.

Query type: {query_type}
User query: {query_text}

Reranked precedent excerpts (top {n_hits}):
{hit_block}

ALLOWED CITATIONS (use only these, exact match):
{allowed_block}

Return STRICT JSON conforming to the response schema:

  top_answer            - direct answer in <= 8 sentences.
  applicable_law        - bulleted list of statutory provisions,
                          constitutional articles, or doctrinal rules
                          drawn ONLY from the excerpts. Empty list if
                          the excerpts do not name any.
  strongest_labels      - subset of ALLOWED CITATIONS that the answer
                          actually relies on. Required for any precedent
                          you cite as support.
  distinguishable       - list of objects {{label, reason}} for
                          precedents that appear similar but should NOT
                          be followed (different forum, different facts,
                          narrower holding). label MUST be in ALLOWED
                          CITATIONS.
  risk_flags            - short strings naming concerns ("single-bench
                          authority", "no recent ratification", "outcome
                          unclear", "conflict with later authority").
  next_question         - one follow-up question worth asking next.
  next_steps            - 2-5 short, concrete actions the lawyer should
                          take based on this answer.
  confidence            - your honest 0..1 confidence in top_answer."""


_RESPONSE_SCHEMA: dict = {
    "type": "OBJECT",
    "properties": {
        "top_answer":       {"type": "STRING"},
        "applicable_law":   {"type": "ARRAY", "items": {"type": "STRING"}},
        "strongest_labels": {"type": "ARRAY", "items": {"type": "STRING"}},
        "distinguishable":  {
            "type": "ARRAY",
            "items": {
                "type": "OBJECT",
                "properties": {
                    "label":  {"type": "STRING"},
                    "reason": {"type": "STRING"},
                },
                "required": ["label", "reason"],
            },
        },
        "risk_flags":       {"type": "ARRAY", "items": {"type": "STRING"}},
        "next_question":    {"type": "STRING"},
        "next_steps":       {"type": "ARRAY", "items": {"type": "STRING"}},
        "confidence":       {"type": "NUMBER"},
    },
    "required": ["top_answer", "confidence"],
}


_LABEL_RE = re.compile(r"\[[^\[\]]+\]")


# ---------- Helpers ----------

def _new_answer_id() -> str:
    return "rans-" + uuid.uuid4().hex[:12]


def _fmt_hit(r: RankedHit) -> str:
    head_bits = [r.document_title or "(untitled)", r.document_court or "",
                 r.document_citation or "", r.document_date or ""]
    head = " · ".join([b for b in head_bits if b])
    return (
        f"- {head}  score={r.final_score:.3f}  binding={r.binding_level}\n"
        f"  citation: {r.citation_label}\n"
        f"  excerpt:  {r.snippet[:600]}"
    )


def _allowed_map(ranked: List[RankedHit]) -> Dict[str, RankedHit]:
    by_label: Dict[str, RankedHit] = {}
    for r in ranked:
        if r.citation_label:
            by_label.setdefault(r.citation_label, r)
    return by_label


def _fuzzy_match(by_label: Dict[str, RankedHit], label: str) -> RankedHit | None:
    norm = re.sub(r"\s+", "", label or "").lower()
    for k, r in by_label.items():
        if re.sub(r"\s+", "", k).lower() == norm:
            return r
    return None


def _labels_from_text(text: str, allowed: Dict[str, RankedHit]) -> List[str]:
    if not text:
        return []
    out: List[str] = []
    for f in _LABEL_RE.findall(text):
        cand = re.sub(r"\s+", " ", f.strip())
        if cand in allowed:
            out.append(cand)
            continue
        m = _fuzzy_match(allowed, cand)
        if m:
            out.append(m.citation_label)
    return out


def _authorities_from_labels(
    allowed: Dict[str, RankedHit], labels: List[str], tier: str = "strongest",
    reason_by_label: Dict[str, str] | None = None,
) -> List[SupportingAuthority]:
    reason_by_label = reason_by_label or {}
    seen: set[str] = set()
    out: List[SupportingAuthority] = []
    for lab in labels:
        cand = re.sub(r"\s+", " ", (lab or "").strip())
        r = allowed.get(cand) or _fuzzy_match(allowed, cand)
        if not r or r.document_id in seen:
            continue
        seen.add(r.document_id)
        out.append(SupportingAuthority(
            document_id=r.document_id,
            title=r.document_title or "(untitled)",
            citation=r.document_citation or "",
            court=r.document_court or "",
            date_decided=r.document_date,
            binding_level=r.binding_level,
            relevance_summary="",   # filled by caller
            top_chunk_citation_label=r.citation_label,
            similarity_score=r.final_score,
            risk_flags=[],
            tier=tier,  # type: ignore[arg-type]
            distinguishing_reason=reason_by_label.get(cand, ""),
        ))
    return out


def _excerpts_from_labels(
    allowed: Dict[str, RankedHit], labels: List[str], max_n: int = 6,
) -> List[Excerpt]:
    seen: set[str] = set()
    out: List[Excerpt] = []
    for lab in labels:
        cand = re.sub(r"\s+", " ", (lab or "").strip())
        r = allowed.get(cand) or _fuzzy_match(allowed, cand)
        if not r or r.citation_label in seen:
            continue
        seen.add(r.citation_label)
        out.append(Excerpt(
            citation_label=r.citation_label,
            document_id=r.document_id,
            chunk_id=r.chunk_id,
            page_start=r.page_start,
            page_end=r.page_end,
            snippet=r.snippet[:500],
        ))
        if len(out) >= max_n:
            break
    return out


# ---------- Synthesisers ----------

def _via_gemini(query: ResearchQuery, ranked: List[RankedHit]) -> ResearchAnswer | None:
    client, kind = get_gemini_client()
    if client is None:
        return None
    try:
        from google.genai import types  # type: ignore
    except ImportError:
        return None

    top = ranked[:8]
    allowed = _allowed_map(top)
    allowed_block = ("\n".join(f"  - {lab}" for lab in allowed.keys())
                     if allowed else "  (no allowed citations — answer must say so)")
    hit_block = "\n".join(_fmt_hit(r) for r in top) or "  (no hits)"

    prompt = _PROMPT.format(
        query_type=query.query_type,
        query_text=query.query_text,
        n_hits=len(top),
        hit_block=hit_block,
        allowed_block=allowed_block,
    )

    try:
        resp = client.models.generate_content(
            model=gemini_model("research_synthesis"),
            contents=[prompt],
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=_RESPONSE_SCHEMA,
                temperature=0.1,
            ),
        )
    except Exception as exc:
        if looks_like_auth_error(exc):
            mark_vertex_failed(str(exc))
        log.error("Gemini synthesis call failed ({}). Using fallback.", exc)
        return None

    raw = (getattr(resp, "text", "") or "").strip()
    if not raw:
        log.warning("Gemini returned empty synthesis. Using fallback.")
        return None
    try:
        data = _json.loads(raw)
    except Exception as exc:
        log.warning("Gemini synthesis JSON parse failed ({}). Using fallback.", exc)
        return None

    top_answer = str(data.get("top_answer", "")).strip()
    declared_strong = list(data.get("strongest_labels") or [])
    distinguishable_raw = list(data.get("distinguishable") or [])
    distinguishable_labels: List[str] = []
    reason_by_label: Dict[str, str] = {}
    for item in distinguishable_raw:
        if isinstance(item, dict):
            lab = str(item.get("label", "")).strip()
            reason = str(item.get("reason", "")).strip()
            if lab:
                distinguishable_labels.append(lab)
                if reason:
                    reason_by_label[
                        re.sub(r"\s+", " ", lab)
                    ] = reason
    # Recovery: harvest any allowed labels mentioned in prose but not
    # listed in strongest_labels. Distinguishable already comes structured.
    recovered = _labels_from_text(top_answer, allowed)

    def _normalise(labels: List[str]) -> List[str]:
        out: List[str] = []
        seen: set[str] = set()
        for lab in labels:
            cand = re.sub(r"\s+", " ", (lab or "").strip())
            if cand and cand not in seen and (
                cand in allowed or _fuzzy_match(allowed, cand)
            ):
                out.append(cand)
                seen.add(cand)
        return out

    strong = _normalise(declared_strong + recovered)
    distinguishable = _normalise(distinguishable_labels)
    # Strongest takes precedence — if a label appears in both, drop it
    # from distinguishable.
    distinguishable = [d for d in distinguishable if d not in set(strong)]

    strong_auths = _authorities_from_labels(allowed, strong, tier="strongest")
    dist_auths = _authorities_from_labels(
        allowed, distinguishable, tier="distinguishable",
        reason_by_label=reason_by_label,
    )

    def _annotate(authorities: List[SupportingAuthority]) -> None:
        for a in authorities:
            match = allowed.get(a.top_chunk_citation_label)
            if match:
                a.relevance_summary = (
                    f"{match.chunk_type.replace('_', ' ').title()} excerpt; "
                    f"binding={match.binding_level}; "
                    f"fact_overlap={match.breakdown.fact_similarity:.2f}, "
                    f"issue_overlap={match.breakdown.issue_overlap:.2f}, "
                    f"doctrinal={match.breakdown.doctrinal_relevance:.2f}"
                )
    _annotate(strong_auths)
    _annotate(dist_auths)

    excerpts = _excerpts_from_labels(allowed, strong + distinguishable)
    risk_flags = [str(x).strip() for x in (data.get("risk_flags") or []) if str(x).strip()]
    prose_labels = len(_LABEL_RE.findall(top_answer))
    if prose_labels and not strong_auths and not dist_auths:
        risk_flags.append(
            f"Answer text references {prose_labels} citation token(s) but "
            "none could be matched to the retrieval set."
        )

    applicable_law = [str(x).strip() for x in (data.get("applicable_law") or [])
                      if str(x).strip()]
    next_steps = [str(x).strip() for x in (data.get("next_steps") or [])
                  if str(x).strip()]

    return ResearchAnswer(
        answer_id=_new_answer_id(),
        query_text=query.query_text,
        query_type=query.query_type,
        top_answer=top_answer,
        applicable_law=applicable_law,
        strongest_authorities=strong_auths,
        distinguishable_authorities=dist_auths,
        authorities=strong_auths,  # back-compat alias
        excerpts=excerpts,
        risk_flags=risk_flags,
        confidence=max(0.0, min(1.0, float(data.get("confidence", 0.5)))),
        retrieval_summary={
            "hits_considered": len(ranked),
            "strongest_grounded": len(strong_auths),
            "distinguishable_grounded": len(dist_auths),
            "excerpts_attached": len(excerpts),
        },
        synthesis_source=kind or "vertex",  # type: ignore[arg-type]
        generated_at=datetime.utcnow(),
        next_question=str(data.get("next_question", "")).strip(),
        next_steps=next_steps,
    )


def _fallback(query: ResearchQuery, ranked: List[RankedHit]) -> ResearchAnswer:
    """Deterministic synthesis path used when no LLM is available.

    We split tiers using a simple, defensible rule: top-3 reranked hits are
    "strongest", and any subsequent hits whose final_score is at least 50%
    of the top hit's score but whose outcome conflicts with the top hit
    are marked "distinguishable". Pure conservative — when in doubt the
    fallback names a precedent rather than hides it.
    """
    if not ranked:
        return ResearchAnswer(
            answer_id=_new_answer_id(),
            query_text=query.query_text,
            query_type=query.query_type,
            top_answer=("No precedents in the corpus matched your query. "
                        "Try broadening filters or ingesting more sources."),
            applicable_law=[],
            strongest_authorities=[], distinguishable_authorities=[],
            authorities=[], excerpts=[],
            risk_flags=["empty_retrieval"],
            confidence=0.0,
            retrieval_summary={"hits_considered": 0,
                               "strongest_grounded": 0,
                               "distinguishable_grounded": 0,
                               "excerpts_attached": 0},
            synthesis_source="fallback",
            generated_at=datetime.utcnow(),
            next_question="Re-phrase using a specific issue tag, court, or date range.",
            next_steps=["Ingest more precedents into the corpus.",
                        "Broaden jurisdiction or date-range filters."],
        )

    strong_hits = ranked[:3]
    threshold = strong_hits[0].final_score * 0.5
    dist_hits = [r for r in ranked[3:] if r.final_score >= threshold][:2]

    def _to_auth(r: RankedHit, tier: str,
                 reason: str = "") -> SupportingAuthority:
        return SupportingAuthority(
            document_id=r.document_id,
            title=r.document_title or "(untitled)",
            citation=r.document_citation,
            court=r.document_court,
            date_decided=r.document_date,
            binding_level=r.binding_level,
            relevance_summary=(
                f"Reranker match (fact={r.breakdown.fact_similarity:.2f}, "
                f"issue={r.breakdown.issue_overlap:.2f}, "
                f"doctrinal={r.breakdown.doctrinal_relevance:.2f}, "
                f"court={r.breakdown.court_rank:.2f})."
            ),
            top_chunk_citation_label=r.citation_label,
            similarity_score=r.final_score,
            risk_flags=[],
            tier=tier,  # type: ignore[arg-type]
            distinguishing_reason=reason,
        )

    strong_auths = [_to_auth(r, "strongest") for r in strong_hits]
    dist_auths = [
        _to_auth(
            r, "distinguishable",
            reason=("Lower multi-factor score and/or weaker authority tier "
                    "than the top hits — confirm forum and facts."),
        )
        for r in dist_hits
    ]

    excerpts = [Excerpt(
        citation_label=r.citation_label,
        document_id=r.document_id,
        chunk_id=r.chunk_id,
        page_start=r.page_start, page_end=r.page_end,
        snippet=r.snippet[:500],
    ) for r in strong_hits + dist_hits]

    top = strong_hits[0]
    body = (
        f"Top retrieved authority for your query: {top.document_title or '(untitled)'} "
        f"({top.document_citation or 'no citation'}) — {top.document_court or 'court unknown'}.\n\n"
        f"Excerpt {top.citation_label}:\n\"{top.snippet[:480]}\"\n\n"
        f"Additional authorities: "
        + ", ".join(r.citation_label for r in strong_hits[1:])
    )
    return ResearchAnswer(
        answer_id=_new_answer_id(),
        query_text=query.query_text,
        query_type=query.query_type,
        top_answer=body,
        applicable_law=[],
        strongest_authorities=strong_auths,
        distinguishable_authorities=dist_auths,
        authorities=strong_auths,  # back-compat
        excerpts=excerpts,
        risk_flags=["fallback_synthesis"],
        confidence=round(min(0.7, top.final_score * 0.9), 3),
        retrieval_summary={
            "hits_considered": len(ranked),
            "strongest_grounded": len(strong_auths),
            "distinguishable_grounded": len(dist_auths),
            "excerpts_attached": len(excerpts),
        },
        synthesis_source="fallback",
        generated_at=datetime.utcnow(),
        next_question="",
        next_steps=[
            "Verify the top authority is still good law (no overruling).",
            "Pull the binding-tier precedents for direct quotation.",
            "If outcome differs from your fact pattern, prepare distinguishing arguments.",
        ],
    )


def synthesize(case_id: int | str, query: ResearchQuery,
               ranked: List[RankedHit]) -> ResearchAnswer:
    """case_id is accepted but unused by the synthesiser itself; kept in
    the signature so the page calls all four services with the same arg
    convention."""
    _ = case_id  # parity with other services
    ans = _via_gemini(query, ranked)
    if ans is not None and ans.top_answer.strip():
        return ans
    fallback = _fallback(query, ranked)
    # If the circuit breaker tripped, label the answer accordingly so the
    # UI can show a credential-rotation hint instead of pretending the
    # output is normal.
    from modules.evidence_vault.services.ai_extractor import (
        _AUTH_FAILED, _AUTH_FAILED_REASON,
    )
    if _AUTH_FAILED:
        flag = ("llm_unavailable: Vertex auth rejected by Google. "
                "Rotate the service-account key (or set GEMINI_API_KEY) "
                "for LLM-quality answers.")
        if flag not in fallback.risk_flags:
            fallback.risk_flags.insert(0, flag)
        if _AUTH_FAILED_REASON:
            detail = f"auth_error_detail: {_AUTH_FAILED_REASON}"
            if detail not in fallback.risk_flags:
                fallback.risk_flags.append(detail)
    return fallback
