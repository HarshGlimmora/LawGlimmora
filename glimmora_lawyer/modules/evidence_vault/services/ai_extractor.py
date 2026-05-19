"""Gemini-powered entity extractor with a deterministic regex fallback.

Priority order at runtime:
  1. Vertex AI Gemini    if USE_VERTEX_AI=true (or a base64-encoded SA JSON is
                          provided in GCP_PROJECT, which gets auto-bootstrapped).
  2. Google AI Studio    if GEMINI_API_KEY is set.
  3. Deterministic regex (always available).

The same return shape (`list[GeminiEntity]`) is produced by all three paths
so the orchestrator does not branch.

Circuit breaker
---------------
Google rejects bad JWTs at the *first* generate_content call, not at client
construction. To avoid paying that round-trip on every research query, we
expose `mark_vertex_failed(reason)` / `looks_like_auth_error(exc)` and a
process-global breaker. Consumers (synthesis, entity extraction, metadata)
call `mark_vertex_failed` inside their exception handlers; once tripped,
`get_gemini_client()` short-circuits to `(None, None)` for the rest of the
process. Check or refresh the state via GET /api/health/llm?probe=true.

Credential rotation guide
-------------------------
If /api/health/llm reports `auth_failed: true`, the SA key in `.env` has
been revoked or rotated server-side in GCP IAM. To recover:

  Option A — new SA key (preferred for shared deploys)
    1. GCP Console → IAM → Service Accounts → pick your SA (currently
       glimmora-projects@design-glimmora-494214.iam.gserviceaccount.com)
       → Keys → Add Key → Create new (JSON).
    2. base64-encode the downloaded JSON:
         base64 -w0 /path/to/key.json
    3. Replace the GCP_PROJECT value in .env with the encoded string.
    4. Restart uvicorn. The bootstrap will re-write .secrets/gcp_sa.json
       and clear the breaker on next process start.

  Option B — AI Studio API key (zero-cost path for local dev)
    1. Get a key from https://aistudio.google.com/app/apikey
    2. Add to .env:  GEMINI_API_KEY=...
    3. Unset USE_VERTEX_AI (or set to false) so the bootstrap doesn't
       prefer the dead Vertex creds. Restart uvicorn.

  Option C — gcloud ADC (no key file on disk)
    1. `gcloud auth application-default login`
    2. Unset GCP_PROJECT's base64 SA JSON; leave the plain project_id.
    3. Restart uvicorn.

The breaker is cleared by process restart only — that matches the
cadence of credential rotation and keeps the runtime decision-tree
trivial.
"""
from __future__ import annotations

import base64
import json
import os
import re
import threading
from pathlib import Path
from typing import List, Optional

from loguru import logger

from config.settings import SETTINGS
from modules.evidence_vault.schemas.entity_schema import (
    GeminiEntity, GeminiEntityList,
)


# ---------- Config probe + credentials bootstrap ----------

def _truthy(v: str | None) -> bool:
    return (v or "").strip().lower() in {"1", "true", "yes", "on"}


_BOOTSTRAPPED = False
_BOOTSTRAP_LOCK = threading.Lock()


_FALSY_USE_VERTEX = {"0", "false", "no", "off"}


def _bootstrap_credentials() -> None:
    """If GCP_PROJECT looks like a base64-encoded service-account JSON,
    decode it to a private file, set GOOGLE_APPLICATION_CREDENTIALS, and
    overwrite GCP_PROJECT with the real project_id. Idempotent.

    Honours `USE_VERTEX_AI=false` as a hard opt-out: an explicit false
    means "don't even try to bootstrap Vertex", which is the safety valve
    when the embedded SA key is stale or revoked.

    Thread safety: guarded by `_BOOTSTRAP_LOCK`. The `_BOOTSTRAPPED` flag
    is set to True ONLY after the env mutation completes — without this,
    a second thread can observe the flag and proceed to read `GCP_PROJECT`
    while it is still the raw base64 string, then construct a Vertex
    client with the entire base64 blob as the project id. That client
    fails with HTTP 403 PERMISSION_DENIED on the first generate_content
    call (~60s later, after retries inside the SDK).
    """
    global _BOOTSTRAPPED
    if _BOOTSTRAPPED:
        return
    with _BOOTSTRAP_LOCK:
        # Re-check inside the lock — another thread may have completed
        # bootstrap while we waited on the lock.
        if _BOOTSTRAPPED:
            return

        use_vertex_env = (os.getenv("USE_VERTEX_AI") or "").strip().lower()
        if use_vertex_env in _FALSY_USE_VERTEX:
            # User explicitly disabled Vertex — don't decode the SA or set creds.
            _BOOTSTRAPPED = True
            return

        raw = (os.getenv("GCP_PROJECT") or "").strip()
        if not raw or len(raw) < 60:
            _BOOTSTRAPPED = True
            return  # Plain project_id or empty — nothing to bootstrap.

        looks_b64 = bool(re.fullmatch(r"[A-Za-z0-9+/=\s]+", raw))
        if not looks_b64:
            _BOOTSTRAPPED = True
            return

        try:
            decoded = base64.b64decode(raw, validate=False).decode("utf-8")
            data = json.loads(decoded)
        except Exception as exc:
            logger.bind(scope="evidence.entity").warning(
                "GCP_PROJECT looked base64-ish but could not be decoded as JSON: {}", exc,
            )
            _BOOTSTRAPPED = True
            return

        project_id = data.get("project_id")
        if not project_id:
            logger.bind(scope="evidence.entity").warning(
                "Decoded GCP_PROJECT JSON has no project_id — leaving env untouched.",
            )
            _BOOTSTRAPPED = True
            return

        secrets_dir = SETTINGS.root_dir / ".secrets"
        secrets_dir.mkdir(parents=True, exist_ok=True)
        sa_path = secrets_dir / "gcp_sa.json"
        sa_path.write_text(decoded, encoding="utf-8")
        try:
            sa_path.chmod(0o600)
        except Exception:
            pass

        os.environ["GCP_PROJECT"] = project_id
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = str(sa_path)
        # Implicit opt-in when the user hasn't expressed a preference: an
        # SA JSON was provided, so default to using it. (Explicit false
        # was filtered above.)
        if not _truthy(os.getenv("USE_VERTEX_AI")):
            os.environ["USE_VERTEX_AI"] = "true"
        # Set the "done" flag LAST so other threads waiting on the lock
        # see a fully-mutated env when they re-check inside the critical
        # section.
        _BOOTSTRAPPED = True
        logger.bind(scope="evidence.entity").info(
            "Bootstrapped Vertex credentials: project={} sa={}",
            project_id, sa_path,
        )


def use_vertex() -> bool:
    _bootstrap_credentials()
    return _truthy(os.getenv("USE_VERTEX_AI")) and bool(os.getenv("GCP_PROJECT"))


def use_aistudio() -> bool:
    _bootstrap_credentials()
    return bool(os.getenv("GEMINI_API_KEY"))


# Per-stage model registry. Each pipeline stage picks the cheapest model
# that can do its job — flash for structured extraction (no reasoning
# needed), pro for free-form reasoning (chat, narrative report, cited
# synthesis). Override any stage with GEMINI_MODEL_<STAGE>=… in .env.
_DEFAULTS_BY_STAGE = {
    "entity_extraction":  "gemini-2.5-flash",   # structured JSON, no reasoning
    "research_metadata":  "gemini-2.5-flash",   # structured JSON, no reasoning
    "chat_synthesis":     "gemini-2.5-pro",     # citation-grounded reasoning
    "final_report":       "gemini-2.5-pro",     # long-form narrative
    "research_synthesis": "gemini-2.5-pro",     # cited research synthesis
}


def gemini_model(stage: Optional[str] = None) -> str:
    """Resolve the model name for a given pipeline stage.

    Resolution order (highest to lowest priority):
      1. `GEMINI_MODEL_<STAGE>` env var  (user override per stage)
      2. _DEFAULTS_BY_STAGE[stage]       (curated default per stage)
      3. `GEMINI_MODEL` env var          (legacy global; only used when
                                          callers don't pass a stage)
      4. Hard fallback                   ("gemini-2.5-flash")
    """
    if stage:
        explicit = (os.getenv(f"GEMINI_MODEL_{stage.upper()}") or "").strip()
        if explicit:
            return explicit
        curated = _DEFAULTS_BY_STAGE.get(stage)
        if curated:
            return curated
    return os.getenv("GEMINI_MODEL", "gemini-2.5-flash")


# Locations to try in order. Override the first via GCP_LOCATION.
_LOCATION_FALLBACKS = [
    "us-central1", "us-east5", "asia-south1", "asia-southeast1",
    "europe-west4", "us-west1",
]


# ---------- Gemini client (lazy) ----------

_client = None
_client_kind: Optional[str] = None
_CLIENT_LOCK = threading.Lock()

# Circuit-breaker: once a call has failed with an auth-style error
# (e.g. "invalid_grant: Invalid JWT Signature" from a revoked SA key),
# every subsequent get_gemini_client() returns (None, None) so callers
# skip straight to the deterministic fallback. Recoverable only by a
# process restart — which is the right cadence, since fixing the auth
# means dropping a new key into .env or running ADC login.
_AUTH_FAILED: bool = False
_AUTH_FAILED_REASON: Optional[str] = None


_AUTH_ERROR_SIGNATURES = (
    "invalid_grant",
    "Invalid JWT",
    "Could not load credentials",
    "DefaultCredentialsError",
    "PermissionDenied",
    "Reauthentication is needed",
    "UNAUTHENTICATED",
)


def mark_vertex_failed(reason: str) -> None:
    """Trip the circuit breaker. Idempotent — first reason wins so the
    /api/health/llm endpoint can show the original failure. Safe to call
    from any consumer (synthesis, entity extraction, metadata)."""
    global _AUTH_FAILED, _AUTH_FAILED_REASON
    if _AUTH_FAILED:
        return
    _AUTH_FAILED = True
    _AUTH_FAILED_REASON = (reason or "").strip()[:300]
    logger.bind(scope="evidence.entity").warning(
        "Vertex auth circuit-breaker tripped: {}", _AUTH_FAILED_REASON,
    )


def looks_like_auth_error(exc: BaseException | str) -> bool:
    """Heuristic match against Google's various auth error shapes."""
    msg = str(exc) or ""
    return any(sig in msg for sig in _AUTH_ERROR_SIGNATURES)


def llm_status() -> dict:
    """Snapshot for the /api/health/llm endpoint. Never leaks secrets —
    only configuration shape + breaker state."""
    _bootstrap_credentials()
    return {
        "vertex_configured": bool(os.getenv("GCP_PROJECT"))
                             and _truthy(os.getenv("USE_VERTEX_AI")),
        "aistudio_configured": bool(os.getenv("GEMINI_API_KEY")),
        "project_id": os.getenv("GCP_PROJECT") or None,
        "location": os.getenv("GCP_LOCATION") or None,
        "model": gemini_model(),
        "client_kind": _client_kind,
        "auth_failed": _AUTH_FAILED,
        "auth_failed_reason": _AUTH_FAILED_REASON,
    }


def _candidate_locations() -> list[str]:
    primary = (os.getenv("GCP_LOCATION") or "").strip()
    out: list[str] = []
    if primary:
        out.append(primary)
    for loc in _LOCATION_FALLBACKS:
        if loc not in out:
            out.append(loc)
    return out


def get_gemini_client():
    """Public accessor — shared by entity extraction and answer synthesis."""
    return _get_client()


def _get_client():
    """Return (client, kind). Thread-safe.

    Locks the construction path so worker threads cannot each build a
    fresh client in parallel — if they did, two slightly-out-of-order
    env reads could produce two different `_client` objects, with one of
    them holding a stale (or wrong-project) configuration. The lock plus
    the inner `_client is not None` re-check make construction strictly
    single-shot per process.
    """
    global _client, _client_kind
    if _AUTH_FAILED:
        return None, None
    if _client is not None:
        return _client, _client_kind

    with _CLIENT_LOCK:
        # Re-check inside the lock: another thread may have built it.
        if _AUTH_FAILED:
            return None, None
        if _client is not None:
            return _client, _client_kind
        try:
            from google import genai  # type: ignore
        except ImportError:
            logger.bind(scope="evidence.entity").warning(
                "google-genai not installed — using regex fallback."
            )
            return None, None

        bound = logger.bind(scope="evidence.entity")
        if use_vertex():
            last_err: Exception | None = None
            project_id = os.getenv("GCP_PROJECT")
            for loc in _candidate_locations():
                try:
                    _client = genai.Client(
                        vertexai=True,
                        project=project_id,
                        location=loc,
                    )
                    _client_kind = "vertex"
                    os.environ["GCP_LOCATION"] = loc  # remember what worked
                    bound.info(
                        "Vertex client ready: project={} location={} model={}",
                        project_id, loc, gemini_model(),
                    )
                    return _client, _client_kind
                except Exception as exc:
                    last_err = exc
                    bound.warning("Vertex init failed at location={}: {}",
                                  loc, exc)
            bound.error("All Vertex locations failed. Last error: {}",
                        last_err)
        if use_aistudio():
            try:
                _client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
                _client_kind = "aistudio"
                bound.info("AI Studio client ready: model={}", gemini_model())
                return _client, _client_kind
            except Exception as exc:
                bound.error("AI Studio init failed: {}. Falling back to regex.",
                            exc)
        return None, None


# ---------- Prompt ----------

_PROMPT = """You are a legal entity extraction engine for Indian legal documents.
Extract every entity from the given chunk that matches one of these types:

PERSON, ORG, COURT, CASE_NUMBER, LAW, ACT, SECTION, RULE, CLAUSE, DATE,
EVENT, LOCATION, AMOUNT, EVIDENCE_ITEM, WITNESS, POLICE_STATION,
FIR_NUMBER, ORDER_NUMBER.

For each entity provide:
  - entity_type        (exactly one of the labels above)
  - value              (text as it appears in the chunk)
  - normalized_value   (canonical form: ISO date for DATE, numeric for AMOUNT,
                         "Section 73" for SECTION, "Indian Contract Act, 1872"
                         for ACT, etc. Empty string if no normalization fits.)
  - context_excerpt    (5-20 word window around the entity from the chunk)
  - confidence         (0.0-1.0; calibrate honestly)

Hard rules:
  * Only extract entities that are LITERALLY present in the chunk.
  * Do not invent, infer, or paraphrase.
  * Do not return entities of any type other than those listed.
  * If nothing qualifies, return an empty entities list.

Chunk text:
\"\"\"
{chunk_text}
\"\"\"
"""


# ---------- Public API ----------

def extract_entities(chunk_text: str) -> tuple[List[GeminiEntity], str]:
    """Returns (entities, source_label).

    source_label is one of "vertex", "aistudio", "regex". Every chunk is
    fully processed via Gemini when available — there is no time-based
    bypass. Throughput is achieved upstream in `entity_extraction_service`
    via batching + concurrency, not by giving up on chunks.
    """
    client, kind = _get_client()
    if client is None:
        return _regex_extract(chunk_text), "regex"
    return _gemini_extract(client, kind, chunk_text)


_GEMINI_SCHEMA: dict = {
    "type": "OBJECT",
    "properties": {
        "entities": {
            "type": "ARRAY",
            "items": {
                "type": "OBJECT",
                "properties": {
                    "entity_type": {
                        "type": "STRING",
                        "enum": [
                            "PERSON", "ORG", "COURT", "CASE_NUMBER", "LAW",
                            "ACT", "SECTION", "RULE", "CLAUSE", "DATE",
                            "EVENT", "LOCATION", "AMOUNT", "EVIDENCE_ITEM",
                            "WITNESS", "POLICE_STATION", "FIR_NUMBER",
                            "ORDER_NUMBER",
                        ],
                    },
                    "value":             {"type": "STRING"},
                    "normalized_value":  {"type": "STRING"},
                    "context_excerpt":   {"type": "STRING"},
                    "confidence":        {"type": "NUMBER"},
                },
                "required": ["entity_type", "value"],
            },
        }
    },
    "required": ["entities"],
}


def _gemini_extract(client, kind: str, chunk_text: str) -> tuple[List[GeminiEntity], str]:
    import json as _json
    from google.genai import types  # type: ignore

    bound = logger.bind(scope="evidence.entity")
    try:
        resp = client.models.generate_content(
            model=gemini_model("entity_extraction"),
            contents=[_PROMPT.format(chunk_text=chunk_text[:12000])],
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=_GEMINI_SCHEMA,
                temperature=0.0,
            ),
        )
    except Exception as exc:
        if looks_like_auth_error(exc):
            mark_vertex_failed(str(exc))
        bound.error("Gemini call failed ({}). Falling back to regex.", exc)
        return _regex_extract(chunk_text), "regex"

    text = (getattr(resp, "text", "") or "").strip()
    if not text:
        bound.warning("Gemini returned empty response. Falling back to regex.")
        return _regex_extract(chunk_text), "regex"
    try:
        data = _json.loads(text)
        parsed = GeminiEntityList.model_validate(data)
    except Exception as exc:
        bound.warning(
            "Gemini returned unparseable response ({}). Falling back to regex.", exc,
        )
        return _regex_extract(chunk_text), "regex"
    bound.info("Gemini ({}) returned {} entities", kind, len(parsed.entities))
    return list(parsed.entities), kind


# ---------- Regex fallback ----------

_INDIAN_CITIES = {
    "Mumbai", "New Delhi", "Delhi", "Pune", "Bengaluru", "Bangalore", "Chennai",
    "Hyderabad", "Kolkata", "Ahmedabad", "Jaipur", "Lucknow", "Chandigarh",
    "Indore", "Bhopal", "Patna", "Nagpur", "Surat", "Kanpur", "Coimbatore",
    "Vadodara", "Visakhapatnam", "Goa", "Panaji", "Gurugram", "Gurgaon",
    "Noida", "Faridabad",
}
_COURTS = [
    "Supreme Court of India", "Delhi High Court", "Bombay High Court",
    "Calcutta High Court", "Madras High Court", "Karnataka High Court",
    "Allahabad High Court", "Gujarat High Court",
    "Punjab and Haryana High Court", "Punjab & Haryana High Court",
    "Telangana High Court", "Kerala High Court",
    "National Company Law Tribunal", "NCLT", "NCLAT",
]

_RE_PERSON = re.compile(
    r"\b(?:Mr|Ms|Mrs|Miss|Dr|Shri|Smt|Sri)\.?\s+"
    r"([A-Z][A-Za-z'\.]+(?:\s+[A-Z][A-Za-z'\.]+){0,3})"
)
_RE_ORG = re.compile(
    r"\b([A-Z][A-Za-z0-9& ]+?\s+(?:Pvt\.?\s+Ltd\.?|Private\s+Limited|"
    r"LLP|Ltd\.?|Limited|Inc\.?|Corp\.?|Co\.?|Trust|Foundation))\b"
)
_RE_WITNESS = re.compile(r"\b(PW[-\s]?\d+|DW[-\s]?\d+|CW[-\s]?\d+)\b")
_RE_CASE_NUMBER = re.compile(
    r"\b(?:Civil Suit|Crl\.?(?:\s*A\.?)?|W\.?P\.?\(?[A-Z]?\)?|S\.?L\.?P\.?(?:\(?[A-Z]?\)?)?|"
    r"First Appeal|Second Appeal|RFA|FAO|CRP|OS|CS|CC)\s*"
    r"(?:No\.?\s*)?\d+(?:\s*[/-]\s*\d{2,4})?",
    re.I,
)
_RE_FIR = re.compile(r"\bFIR\s*(?:No\.?\s*)?\d+(?:[/-]\d{2,4})?\b", re.I)
_RE_ORDER = re.compile(r"\bOrder\s*(?:No\.?\s*)?\d+(?:[/-]\d{2,4})?\b", re.I)
_RE_AMOUNT = re.compile(
    r"(?:(?:Rs\.?|INR|₹)\s*)?"
    r"\d{1,3}(?:[,]\d{2,3})+(?:\.\d+)?\s*(?:crore|crores|lakh|lakhs|million|thousand)?"
    r"|(?:Rs\.?|INR|₹)\s*\d+(?:\.\d+)?(?:\s*(?:crore|crores|lakh|lakhs))?",
    re.I,
)
_RE_ACT = re.compile(
    r"(?:The\s+)?[A-Z][A-Za-z' ,&-]{2,60}?\s+Act,?\s*\d{4}"
)
_RE_SECTION = re.compile(
    r"(?:Section|Sec\.?|s\.)\s*\d+[A-Za-z]*(?:\(\d+\))?",
    re.I,
)
_RE_ARTICLE = re.compile(r"\bArticle\s+\d+[A-Z]?(?:\(\d+\))?", re.I)
_RE_RULE = re.compile(r"\bRule\s+\d+(?:\([0-9A-Za-z]+\))?", re.I)
_RE_CLAUSE = re.compile(r"\b[Cc]lause\s+\d+(?:\.\d+)*\b")
_RE_DATE_N = re.compile(r"\b\d{1,2}[-/.]\d{1,2}[-/.]\d{2,4}\b")
_RE_DATE_T = re.compile(
    r"\b\d{1,2}(?:st|nd|rd|th)?\s+"
    r"(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)[a-z]*\.?\s+\d{4}\b",
    re.I,
)
_RE_DATE_T2 = re.compile(
    r"\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)[a-z]*\.?\s+\d{1,2},?\s+\d{4}\b",
    re.I,
)
_RE_POLICE = re.compile(
    r"\b([A-Z][A-Za-z]+(?:\s+[A-Z][A-Za-z]+)?)\s+Police\s+Station\b|\bPS\s+([A-Z][A-Za-z]+)\b"
)
_RE_EXHIBIT = re.compile(r"\b(?:Annexure|Exhibit)\s+[A-Z0-9-]+\b", re.I)
_EVENT_VERBS = (
    "executed", "signed", "filed", "issued", "served", "received",
    "paid", "deposited", "transferred", "delivered", "assaulted",
    "stated", "alleged", "demanded", "agreed", "terminated",
    "breached", "performed", "arrested",
)
_RE_EVENT = re.compile(rf"\b({'|'.join(_EVENT_VERBS)})\b", re.I)


def _ctx(text: str, m: re.Match) -> str:
    s = max(0, m.start() - 40)
    e = min(len(text), m.end() + 60)
    snippet = text[s:e].replace("\n", " ").strip()
    return re.sub(r"\s+", " ", snippet)


def _make(entity_type: str, value: str, raw_match: str | None, context: str,
          confidence: float = 0.7) -> GeminiEntity:
    return GeminiEntity(
        entity_type=entity_type,  # type: ignore[arg-type]
        value=raw_match or value,
        normalized_value="",  # filled by normalize_value() later
        context_excerpt=context,
        confidence=confidence,
    )


def _regex_extract(text: str) -> List[GeminiEntity]:
    out: List[GeminiEntity] = []
    if not text:
        return out

    def emit(et: str, m: re.Match, conf: float = 0.7) -> None:
        out.append(_make(et, m.group(0), m.group(0), _ctx(text, m), conf))

    # PERSON via title cue
    for m in _RE_PERSON.finditer(text):
        out.append(_make("PERSON", m.group(1), m.group(0), _ctx(text, m), 0.7))

    # ORG (legal-entity suffix)
    for m in _RE_ORG.finditer(text):
        out.append(_make("ORG", m.group(1), m.group(0), _ctx(text, m), 0.7))

    # WITNESS
    for m in _RE_WITNESS.finditer(text):
        emit("WITNESS", m, 0.85)

    # CASE_NUMBER / FIR / ORDER
    for m in _RE_CASE_NUMBER.finditer(text):
        emit("CASE_NUMBER", m, 0.8)
    for m in _RE_FIR.finditer(text):
        emit("FIR_NUMBER", m, 0.85)
    for m in _RE_ORDER.finditer(text):
        emit("ORDER_NUMBER", m, 0.7)

    # AMOUNT
    for m in _RE_AMOUNT.finditer(text):
        emit("AMOUNT", m, 0.75)

    # ACT (and treat as LAW too — both labels covered)
    for m in _RE_ACT.finditer(text):
        emit("ACT", m, 0.7)

    # SECTION / ARTICLE / RULE / CLAUSE
    for m in _RE_SECTION.finditer(text):
        emit("SECTION", m, 0.8)
    for m in _RE_ARTICLE.finditer(text):
        # Articles are legal_basis too — treat under SECTION to keep schema tight,
        # since the schema does not define a separate "ARTICLE" type.
        emit("SECTION", m, 0.75)
    for m in _RE_RULE.finditer(text):
        emit("RULE", m, 0.75)
    for m in _RE_CLAUSE.finditer(text):
        emit("CLAUSE", m, 0.8)

    # DATE
    seen_dates: set[str] = set()
    for pat in (_RE_DATE_N, _RE_DATE_T, _RE_DATE_T2):
        for m in pat.finditer(text):
            if m.group(0) in seen_dates:
                continue
            seen_dates.add(m.group(0))
            emit("DATE", m, 0.85)

    # POLICE_STATION
    for m in _RE_POLICE.finditer(text):
        val = m.group(1) or m.group(2)
        if val:
            out.append(_make("POLICE_STATION", val, m.group(0), _ctx(text, m), 0.7))

    # EVIDENCE_ITEM
    for m in _RE_EXHIBIT.finditer(text):
        emit("EVIDENCE_ITEM", m, 0.75)

    # COURT (list lookup)
    for court in _COURTS:
        for m in re.finditer(rf"\b{re.escape(court)}\b", text):
            out.append(_make("COURT", court, m.group(0), _ctx(text, m), 0.8))

    # LOCATION (city list)
    for city in _INDIAN_CITIES:
        for m in re.finditer(rf"\b{re.escape(city)}\b", text):
            out.append(_make("LOCATION", city, m.group(0), _ctx(text, m), 0.7))

    # EVENT (verb-anchored)
    for m in _RE_EVENT.finditer(text):
        out.append(_make("EVENT", m.group(1).lower(), m.group(0), _ctx(text, m), 0.5))

    return out
