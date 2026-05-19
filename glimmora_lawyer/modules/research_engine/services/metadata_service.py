"""Metadata enrichment for a PrecedentDocument.

Primary path: Vertex AI Gemini with a strict response_schema (same pattern
as Package 1's entity extractor). Fallback path: a deterministic regex
extractor that picks up the most common Indian judgment headers (court,
citation, judges, decision date).

The two paths share the same return shape so the orchestrator does not
branch. After this runs, the document's status moves from "extracted" to
"enriched".
"""
from __future__ import annotations

import json as _json
import re
from datetime import date, datetime
from typing import List, Optional

from loguru import logger

from modules.research_engine.schemas.corpus_schema import (
    PrecedentDocument, PrecedentMeta,
)
from modules.research_engine.services.persistence_service import save_document
from modules.research_engine.utils.court_hierarchy import infer_binding_level
# Reuse Package 1's Vertex/AIStudio bootstrap — no need to duplicate it.
from modules.evidence_vault.services.ai_extractor import (
    gemini_model, get_gemini_client, looks_like_auth_error,
    mark_vertex_failed,
)


log = logger.bind(scope="research.metadata")


# ---------- LLM prompt + schema ----------

_PROMPT = """You are a legal-metadata extractor for Indian court judgments and
precedent documents. Read the document text below and extract structured
metadata. Use ONLY facts present in the text — do not infer or hallucinate.

Document text (first 18,000 chars):
\"\"\"
{body}
\"\"\"

Return STRICT JSON with these fields (use empty string / empty list when
absent):

  title              - case name in the form "X vs Y" or as printed
  citation           - neutral or reporter citation, e.g. "(2019) 5 SCC 412"
  court              - full court name, e.g. "Supreme Court of India"
  judges             - list of judge names (without honorifics)
  date_decided       - ISO date "YYYY-MM-DD" or empty string
  jurisdiction       - "India" by default; else the relevant state/region
  practice_areas     - list of broad practice areas (max 4)
  issue_tags         - list of short issue keywords (max 8)
  outcome            - one of: "allowed", "dismissed", "remanded",
                       "partly_allowed", "settled", "interim", "unknown"
  headnote           - the printed headnote if any, else empty
  ratio              - the ratio decidendi if explicitly stated, else empty"""


_GEMINI_SCHEMA: dict = {
    "type": "OBJECT",
    "properties": {
        "title":          {"type": "STRING"},
        "citation":       {"type": "STRING"},
        "court":          {"type": "STRING"},
        "judges":         {"type": "ARRAY", "items": {"type": "STRING"}},
        "date_decided":   {"type": "STRING"},
        "jurisdiction":   {"type": "STRING"},
        "practice_areas": {"type": "ARRAY", "items": {"type": "STRING"}},
        "issue_tags":     {"type": "ARRAY", "items": {"type": "STRING"}},
        "outcome":        {"type": "STRING"},
        "headnote":       {"type": "STRING"},
        "ratio":          {"type": "STRING"},
    },
    "required": ["title", "court"],
}


# ---------- Public API ----------

def extract_metadata(doc: PrecedentDocument) -> PrecedentMeta:
    """Returns an enriched PrecedentMeta. Never raises — always best-effort.

    The `confidence_score` is a coarse self-assessment derived from how
    many of the headline fields (title, citation, court, date) we could
    populate. It is *not* a calibrated probability — just enough signal
    for the UI to flag low-trust metadata for human review.
    """
    body = (doc.full_text or "")[:18000]
    used_llm = False
    parsed = _via_gemini(body) if body else None
    if parsed is not None:
        used_llm = True
    else:
        parsed = _via_regex(body or "")
    parsed["document_id"] = doc.document_id
    if not parsed.get("title"):
        parsed["title"] = doc.meta.title or doc.filename

    meta = _to_meta(parsed)
    meta.binding_level = infer_binding_level(meta.court)
    # Provenance: keep whatever the upload step set; default if empty.
    meta.source_type = doc.meta.source_type or "pdf_upload"
    meta.source_reference = doc.meta.source_reference or doc.filename
    meta.confidence_score = _confidence(meta, used_llm)
    return meta


def _confidence(meta: PrecedentMeta, used_llm: bool) -> float:
    """Heuristic 0..1 score: 1pt each for title, citation, court, date.
    LLM extraction earns a small multiplier over the regex fallback."""
    filled = sum(1 for v in (meta.title, meta.citation, meta.court,
                             meta.date_decided) if v)
    base = filled / 4.0
    return round(min(1.0, base * (1.0 if used_llm else 0.85)), 3)


def enrich_and_save(case_id: int | str, doc: PrecedentDocument) -> PrecedentDocument:
    """Convenience: extract metadata, attach to doc, persist."""
    meta = extract_metadata(doc)
    doc.meta = meta
    if doc.status in ("extracted", "pending"):
        doc.status = "enriched"
    save_document(case_id, doc)
    return doc


# ---------- LLM path ----------

def _via_gemini(body: str) -> Optional[dict]:
    client, kind = get_gemini_client()
    if client is None:
        return None
    try:
        from google.genai import types  # type: ignore
    except ImportError:
        return None
    try:
        resp = client.models.generate_content(
            model=gemini_model("research_metadata"),
            contents=[_PROMPT.format(body=body)],
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=_GEMINI_SCHEMA,
                temperature=0.0,
            ),
        )
    except Exception as exc:
        if looks_like_auth_error(exc):
            mark_vertex_failed(str(exc))
        log.warning("Gemini metadata call failed ({}). Falling back to regex.", exc)
        return None

    text = (getattr(resp, "text", "") or "").strip()
    if not text:
        log.warning("Gemini metadata returned empty response. Falling back.")
        return None
    try:
        data = _json.loads(text)
    except Exception as exc:
        log.warning("Gemini metadata JSON parse failed ({}). Falling back.", exc)
        return None
    log.info("Gemini metadata ({}) ok: title={!r} court={!r}",
             kind, (data.get("title") or "")[:80], (data.get("court") or "")[:80])
    return data


# ---------- Regex fallback ----------

_RE_VS = re.compile(r"\b([A-Z][^\n\r]{2,80}?)\s+(?:vs?\.?|v\.|versus)\s+"
                    r"([A-Z][^\n\r]{2,80}?)\b", re.I)
_RE_CITATION = re.compile(
    r"\(?\d{4}\)?\s+\d+\s+(?:SCC|SCR|AIR|SCALE|JT|Bom|Del|Mad|Cal|Kar|MP|"
    r"Pat|All|Raj|Guj|Ker|MhLJ)\s*\d*",
    re.I,
)
_RE_AIR = re.compile(r"AIR\s+\d{4}\s+(?:SC|[A-Z][A-Za-z]+)\s+\d+", re.I)
_RE_COURT_LINE = re.compile(
    r"(?im)^(?:in\s+the\s+)?(?P<court>Supreme\s+Court\s+of\s+India|"
    r"[A-Z][A-Za-z ]+High\s+Court(?:\s+at\s+[A-Z][a-z]+)?|"
    r"National\s+Company\s+Law\s+(?:Tribunal|Appellate\s+Tribunal)|"
    r"NCLT|NCLAT|ITAT)\b"
)
_RE_DATE_LINE = re.compile(
    r"(?:Date\s+of\s+(?:Decision|Judgment)|Decided\s+on|Pronounced\s+on)\s*:?\s*"
    r"(?P<d>\d{1,2}[-/.\s][A-Za-z0-9]{1,9}[-/.\s]\d{2,4})",
    re.I,
)
_RE_JUDGE_LINE = re.compile(
    r"(?im)(?:Hon'?ble\s+(?:Mr\.?|Ms\.?|Justice|Mrs\.?)\s*Justice\s+|"
    r"Justice\s+|Hon'?ble\s+Justice\s+)([A-Z][a-zA-Z'\.]+(?:\s+[A-Z][a-zA-Z'\.]+){0,3})"
)


def _via_regex(body: str) -> dict:
    title = ""
    m = _RE_VS.search(body)
    if m:
        title = f"{m.group(1).strip()} vs {m.group(2).strip()}"

    citation = ""
    m = _RE_CITATION.search(body) or _RE_AIR.search(body)
    if m:
        citation = m.group(0).strip()

    court = ""
    m = _RE_COURT_LINE.search(body)
    if m:
        court = m.group("court").strip()

    date_decided = ""
    m = _RE_DATE_LINE.search(body)
    if m:
        iso = _parse_loose_date(m.group("d"))
        if iso:
            date_decided = iso

    judges = list({j.strip() for j in _RE_JUDGE_LINE.findall(body)})[:6]

    return {
        "title": title, "citation": citation, "court": court,
        "judges": judges, "date_decided": date_decided,
        "jurisdiction": "India",
        "practice_areas": [], "issue_tags": [],
        "outcome": "unknown", "headnote": "", "ratio": "",
    }


def _parse_loose_date(s: str) -> Optional[str]:
    s = s.strip()
    for fmt in (
        "%d-%m-%Y", "%d/%m/%Y", "%d.%m.%Y",
        "%d %B %Y", "%d %b %Y", "%d-%B-%Y", "%d-%b-%Y",
        "%B %d, %Y", "%b %d, %Y",
    ):
        try:
            return datetime.strptime(s, fmt).date().isoformat()
        except ValueError:
            continue
    return None


# ---------- Coercion ----------

def _to_meta(data: dict) -> PrecedentMeta:
    raw_date = (data.get("date_decided") or "").strip()
    parsed_date: Optional[date] = None
    if raw_date:
        try:
            parsed_date = date.fromisoformat(raw_date)
        except ValueError:
            parsed_date = None

    def _list(k: str) -> List[str]:
        v = data.get(k) or []
        return [str(x).strip() for x in v if str(x).strip()]

    return PrecedentMeta(
        document_id=str(data.get("document_id") or ""),
        title=str(data.get("title") or "").strip(),
        citation=str(data.get("citation") or "").strip(),
        court=str(data.get("court") or "").strip(),
        judges=_list("judges"),
        date_decided=parsed_date,
        jurisdiction=str(data.get("jurisdiction") or "India").strip() or "India",
        practice_areas=_list("practice_areas"),
        issue_tags=_list("issue_tags"),
        outcome=(str(data.get("outcome") or "").strip() or None),
        headnote=(str(data.get("headnote") or "").strip() or None),
        ratio=(str(data.get("ratio") or "").strip() or None),
    )
