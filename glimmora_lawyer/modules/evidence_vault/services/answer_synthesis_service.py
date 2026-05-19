"""Take a RetrievalContext and produce a citation-backed Answer.

Primary path: Vertex AI Gemini with a strict response schema that mirrors the
Answer fields the UI consumes (final_answer, confidence, warnings,
why_retrieved, next_question).

Fallback path: a deterministic template that quotes the top retrieved chunk
and lists the top three citations. Used when Gemini is unavailable or its
response can't be parsed. The fallback is honest about being mechanical.

In every path, supporting_sources and retrieval_summary are computed from the
retrieved context — never invented.
"""
from __future__ import annotations

import json
import re
import uuid
from typing import Dict, List

from loguru import logger

from modules.evidence_vault.schemas.answer_schema import Answer, SupportingSource
from modules.evidence_vault.schemas.retrieval_schema import (
    RetrievalContext, RetrievalResult,
)
from modules.evidence_vault.services.ai_extractor import (
    gemini_model, get_gemini_client, looks_like_auth_error,
    mark_vertex_failed,
)

log = logger.bind(scope="evidence.synthesis")


def _new_answer_id() -> str:
    return "ans-" + uuid.uuid4().hex[:12]


_PROMPT = """You are Glimmora Lawyer's evidence assistant. You answer ONLY from the
retrieved evidence excerpts provided below — never from prior knowledge.

HARD RULES (legal-trust mode):
  * Do not invent facts, dates, parties, page numbers, or chunk indexes.
  * Cite every claim using ONE of the labels in ALLOWED CITATIONS exactly as
    written. Any label outside that list will be discarded.
  * If the evidence is weak or silent, say so plainly with no citation.
  * Tone: concise, neutral, legal-professional.
  * Never produce more than 6 sentences of final_answer.

User query:
{query}

Inferred intent: {intent}
Retrieval mode: {mode}
Partition filter: {partitions}

Retrieved entity matches ({n_entity}):
{entity_block}

Retrieved chunk excerpts ({n_chunk}):
{chunk_block}

{extras_block}

ALLOWED CITATIONS (use only these, exact match):
{allowed_block}

Return STRICT JSON conforming to the response schema. Do not include any prose
outside the JSON. supporting_citation_labels MUST be a subset of ALLOWED
CITATIONS. If none apply, return an empty supporting_citation_labels and add
a single warning explaining why."""


_LABEL_RE = re.compile(r"\[[^\[\]]+\]")


_RESPONSE_SCHEMA: dict = {
    "type": "OBJECT",
    "properties": {
        "final_answer": {"type": "STRING"},
        "confidence":   {"type": "NUMBER"},
        "warnings": {
            "type": "ARRAY",
            "items": {"type": "STRING"},
        },
        "supporting_citation_labels": {
            "type": "ARRAY",
            "items": {"type": "STRING"},
        },
        "why_retrieved": {"type": "STRING"},
        "next_question": {"type": "STRING"},
    },
    "required": ["final_answer", "confidence"],
}


# ---------- Helpers to build the prompt blocks ----------

def _fmt_entity(r: RetrievalResult) -> str:
    return (
        f"- {r.title}  conf={r.confidence:.2f}\n"
        f"  citation: {r.citation_label}\n"
        f"  context: {r.snippet[:240]}"
    )


def _fmt_chunk(r: RetrievalResult) -> str:
    return (
        f"- {r.title}  conf={r.confidence:.2f}\n"
        f"  citation: {r.citation_label}\n"
        f"  excerpt: {r.snippet[:600]}"
    )


def _build_extras(ctx: RetrievalContext) -> str:
    parts: List[str] = []
    if ctx.contradiction_hits:
        parts.append(f"Contradiction records ({len(ctx.contradiction_hits)}):")
        for r in ctx.contradiction_hits[:4]:
            parts.append(f"  - {r.title} :: {r.snippet[:240]}")
    if ctx.missing_hits:
        parts.append(f"Missing-evidence records ({len(ctx.missing_hits)}):")
        for r in ctx.missing_hits[:4]:
            parts.append(f"  - {r.title} :: {r.snippet[:240]}")
    return "\n".join(parts) if parts else ""


def _allowed_label_map(ctx: RetrievalContext) -> Dict[str, RetrievalResult]:
    """Unique citation label → retrieval row. Used to validate any label the
    model returns AND to recover labels parsed from the answer prose."""
    by_label: Dict[str, RetrievalResult] = {}
    for arr in (ctx.all_results, ctx.entity_hits, ctx.chunk_hits,
                ctx.contradiction_hits, ctx.missing_hits):
        for r in arr:
            by_label.setdefault(r.citation_label, r)
    return by_label


def _supporting_sources(by_label: Dict[str, RetrievalResult],
                        labels: List[str]) -> List[SupportingSource]:
    seen: set[str] = set()
    out: List[SupportingSource] = []
    for label in labels:
        # Tolerant match: strip whitespace + collapse multi-spaces
        candidate = re.sub(r"\s+", " ", (label or "").strip())
        r = by_label.get(candidate)
        if not r and candidate in by_label:
            r = by_label[candidate]
        if not r:
            # Try fuzzy: same filename + same page range + same chunk number
            r = _fuzzy_match(by_label, candidate)
        if not r or r.citation_label in seen:
            continue
        seen.add(r.citation_label)
        out.append(SupportingSource(
            citation_label=r.citation_label,
            document_id=r.source_document_id,
            chunk_id=r.source_chunk_id,
            page=r.source_page,
            snippet=r.snippet[:300],
        ))
    return out


def _fuzzy_match(by_label: Dict[str, RetrievalResult],
                 label: str) -> RetrievalResult | None:
    """Match a label by its components if exact string compare fails."""
    norm = re.sub(r"\s+", "", label or "").lower()
    for k, r in by_label.items():
        if re.sub(r"\s+", "", k).lower() == norm:
            return r
    return None


def _labels_from_text(text: str, allowed: Dict[str, RetrievalResult]) -> List[str]:
    """Pull every `[…]` token from the model's prose and keep only the ones
    that resolve to a real retrieval row."""
    if not text:
        return []
    found = _LABEL_RE.findall(text)
    if not found:
        return []
    out: List[str] = []
    for f in found:
        candidate = re.sub(r"\s+", " ", f.strip())
        if candidate in allowed:
            out.append(candidate)
            continue
        m = _fuzzy_match(allowed, candidate)
        if m:
            out.append(m.citation_label)
    return out


def _retrieval_summary(ctx: RetrievalContext) -> Dict[str, int]:
    return {
        "entity_hits": len(ctx.entity_hits),
        "chunk_hits": len(ctx.chunk_hits),
        "contradiction_hits": len(ctx.contradiction_hits),
        "missing_hits": len(ctx.missing_hits),
    }


# ---------- Synthesisers ----------

def _synthesize_via_gemini(ctx: RetrievalContext) -> Answer | None:
    client, kind = get_gemini_client()
    if client is None:
        return None
    from google.genai import types  # type: ignore

    entity_block = "\n".join(_fmt_entity(r) for r in ctx.entity_hits[:8]) or "  (none)"
    chunk_block = "\n".join(_fmt_chunk(r) for r in ctx.chunk_hits[:6]) or "  (none)"
    extras = _build_extras(ctx)

    allowed_map = _allowed_label_map(ctx)
    unique_labels = sorted(allowed_map.keys())
    allowed_block = ("\n".join(f"  - {lab}" for lab in unique_labels)
                     if unique_labels else "  (no retrieved citations — answer must say so)")

    prompt = _PROMPT.format(
        query=ctx.query, intent=ctx.intent, mode=ctx.mode,
        partitions=", ".join(ctx.partition_filter or []) or "(none)",
        n_entity=len(ctx.entity_hits), n_chunk=len(ctx.chunk_hits),
        entity_block=entity_block, chunk_block=chunk_block,
        extras_block=extras,
        allowed_block=allowed_block,
    )

    try:
        resp = client.models.generate_content(
            model=gemini_model("chat_synthesis"),
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
        data = json.loads(raw)
    except Exception as exc:
        log.warning("Gemini synthesis JSON parse failed ({}). Using fallback.", exc)
        return None

    final_answer = str(data.get("final_answer", "")).strip()
    model_labels = list(data.get("supporting_citation_labels") or [])
    # First pass: validate model-returned labels.
    supports = _supporting_sources(allowed_map, model_labels)
    # Recovery pass: harvest any allowed labels that appear in the answer prose
    # but were not listed in supporting_citation_labels.
    recovered = _labels_from_text(final_answer, allowed_map)
    if recovered:
        merged = [s.citation_label for s in supports] + [
            lab for lab in recovered
            if lab not in {s.citation_label for s in supports}
        ]
        supports = _supporting_sources(allowed_map, merged)

    warnings = list(data.get("warnings") or [])
    # Only warn when the answer prose *names* citations but none of them could
    # be grounded — the more useful signal for the lawyer reading the panel.
    prose_label_count = len(_LABEL_RE.findall(final_answer))
    if prose_label_count and not supports:
        warnings.append(
            f"Answer text references {prose_label_count} citation token(s) "
            "but none could be matched to the retrieval set."
        )
    if not ctx.entity_hits and not ctx.chunk_hits:
        warnings.append("No retrieved evidence — answer may be empty by design.")

    log.info(
        "Gemini synthesis ({}) ok: returned_labels={} recovered_from_prose={} "
        "grounded={}", kind, len(model_labels), len(recovered), len(supports),
    )
    return Answer(
        answer_id=_new_answer_id(),
        query=ctx.query,
        intent=ctx.intent,
        final_answer=final_answer,
        supporting_sources=supports,
        confidence=max(0.0, min(1.0, float(data.get("confidence", 0.5)))),
        warnings=warnings,
        retrieval_summary=_retrieval_summary(ctx),
        why_retrieved=str(data.get("why_retrieved", "")).strip(),
        next_question=str(data.get("next_question", "")).strip(),
        synthesis_source=kind or "vertex",
    )


def _synthesize_fallback(ctx: RetrievalContext) -> Answer:
    """Deterministic template — used when Gemini is unavailable or failed."""
    warnings: List[str] = ["Answer generated by the deterministic fallback "
                           "(no Gemini synthesis). Quoted excerpt is verbatim."]
    top = ctx.all_results[0] if ctx.all_results else None
    if not top:
        return Answer(
            answer_id=_new_answer_id(),
            query=ctx.query, intent=ctx.intent,
            final_answer=("No matching evidence was retrieved in this case for "
                          "your query."),
            supporting_sources=[],
            confidence=0.0,
            warnings=["No retrieval hits at all — try different keywords or "
                      "broaden the partition filter."],
            retrieval_summary=_retrieval_summary(ctx),
            why_retrieved="No entity or chunk matched the query tokens.",
            next_question="Re-phrase using a specific entity (date, party, section).",
            synthesis_source="fallback",
        )
    sources: List[SupportingSource] = []
    for r in ctx.all_results[:3]:
        sources.append(SupportingSource(
            citation_label=r.citation_label,
            document_id=r.source_document_id,
            chunk_id=r.source_chunk_id,
            page=r.source_page,
            snippet=r.snippet[:300],
        ))

    final = (
        f"Top retrieval match for your query was {top.title} "
        f"({top.citation_label}). Quoted excerpt:\n\n"
        f"\"{top.snippet[:600]}\"\n\n"
        f"Additional grounding: "
        + ", ".join(r.citation_label for r in ctx.all_results[1:3])
        + (" ." if len(ctx.all_results) > 1 else "")
    )

    return Answer(
        answer_id=_new_answer_id(),
        query=ctx.query, intent=ctx.intent,
        final_answer=final,
        supporting_sources=sources,
        confidence=round(min(0.85, top.confidence * 0.9), 3),
        warnings=warnings,
        retrieval_summary=_retrieval_summary(ctx),
        why_retrieved=f"Top hit retrieved via {top.result_type} — {top.reason_retrieved}",
        next_question="",
        synthesis_source="fallback",
    )


def synthesize(ctx: RetrievalContext) -> Answer:
    answer = _synthesize_via_gemini(ctx)
    if answer is not None and answer.final_answer.strip():
        return answer
    return _synthesize_fallback(ctx)
