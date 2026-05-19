"""Research & Precedent Engine routes (Package 2).

Project-scoped — every endpoint is mounted under /api/cases/{case_id}/...
The router does not own any business logic; it adapts HTTP into calls on
the modules.research_engine service layer and serialises Pydantic dumps
back out.

Endpoints (concise contract):

  Corpus
    GET    /documents                          list precedent doc_ids
    POST   /upload                             ingest a precedent PDF
    GET    /documents/{document_id}            full PrecedentDocument
    DELETE /documents/{document_id}            remove a precedent
    POST   /documents/{document_id}/enrich     re-run metadata extraction
    POST   /chunk-and-index                    rebuild chunks + indexes
    GET    /metadata                           filterable metadata index
    POST   /index/rebuild                      force rebuild both indexes

  Research
    POST   /search                             retrieve + rerank
    POST   /research                           retrieve + rerank + synthesise

  Sessions
    GET    /sessions                           list saved sessions
    GET    /sessions/{session_id}              one session
    POST   /sessions                           persist (used after /research)
    GET    /sessions/{session_id}/export/{fmt} json | markdown

  Downstream
    POST   /downstream/build                   rebuild + return payload
    GET    /downstream                         return cached payload
"""
from __future__ import annotations

from datetime import date
from typing import List, Optional

from fastapi import APIRouter, Depends, File, Form, Response, UploadFile
from pydantic import BaseModel, Field

from api.deps import require_profile
from api.errors import DomainError
from modules.case.services.case_service import get_case
from modules.research_engine.schemas.retrieval_schema import ResearchQuery
from modules.research_engine.services.chunking_service import (
    build_and_save_chunks,
)
from modules.research_engine.services.export_service import (
    export_session_json, export_session_markdown, export_session_pdf,
)
from modules.research_engine.services.indexing_service import (
    load_metadata_index, rebuild_index,
)
from modules.research_engine.services.metadata_service import enrich_and_save
from modules.research_engine.services.outputs_service import (
    build_downstream, load_downstream,
)
from modules.research_engine.services.persistence_service import (
    delete_document, filename_already_present, list_documents, load_document,
)
from modules.research_engine.services.reranking_service import rerank
from modules.research_engine.services.retrieval_service import search
from modules.research_engine.services.session_service import (
    build_session, list_sessions, load_session, save_session,
    update_session_feedback,
)
from modules.research_engine.services.similarity_service import find_similar
from modules.research_engine.services.synthesis_service import synthesize
from modules.research_engine.services.upload_service import (
    IngestionError, ingest_pdf, ingest_text,
)


router = APIRouter(
    prefix="/api/cases/{case_id}/research",
    tags=["research"],
)


def _ensure_case(case_id: int, uid: int) -> None:
    if not get_case(uid, case_id):
        raise DomainError("case_not_found", "Case not found.", status_code=404)


# ---------- Request models ----------

class SearchBody(BaseModel):
    query_text: str = Field(min_length=1)
    query_type: str = "legal_question"
    jurisdiction_filter: Optional[str] = None
    court_filter: List[str] = Field(default_factory=list)
    issue_filter: List[str] = Field(default_factory=list)
    practice_area_filter: List[str] = Field(default_factory=list)
    date_from: Optional[date] = None
    date_to: Optional[date] = None
    top_k: int = Field(default=15, ge=1, le=100)


class IngestTextBody(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    body: str = Field(min_length=1)
    source_reference: str = ""
    notes: Optional[str] = None


class SaveSessionBody(BaseModel):
    answer_id: str          # for cross-check; we just store everything
    query_text: str
    query_type: str = "legal_question"
    ranked_hits: List[dict] = Field(default_factory=list)
    answer: dict
    user_notes: str = ""
    pinned_document_ids: List[str] = Field(default_factory=list)
    unresolved_questions: List[str] = Field(default_factory=list)


class FeedbackBody(BaseModel):
    pinned_document_ids: Optional[List[str]] = None
    user_feedback: Optional[str] = None      # thumbs_up | thumbs_down | neutral
    unresolved_questions: Optional[List[str]] = None
    user_notes: Optional[str] = None


# ---------- Helpers ----------

def _query_from_body(body: SearchBody) -> ResearchQuery:
    drange = None
    if body.date_from or body.date_to:
        drange = (body.date_from, body.date_to)
    return ResearchQuery(
        query_text=body.query_text.strip(),
        query_type=body.query_type,  # type: ignore[arg-type]
        jurisdiction_filter=body.jurisdiction_filter,
        court_filter=body.court_filter,
        issue_filter=body.issue_filter,
        practice_area_filter=body.practice_area_filter,
        date_range=drange,
        top_k=body.top_k,
    )


# ---------- Corpus ----------

@router.get("/documents")
def list_research_documents(case_id: int,
                            uid: int = Depends(require_profile)) -> list[str]:
    _ensure_case(case_id, uid)
    return list_documents(case_id)


@router.post("/ingest-text")
def post_ingest_text(case_id: int, body: IngestTextBody,
                     uid: int = Depends(require_profile)) -> dict:
    """Ingest a precedent supplied as raw text (no PDF). Mirrors the
    /upload pipeline: extract → enrich → chunk → rebuild index."""
    _ensure_case(case_id, uid)
    doc, log = ingest_text(
        case_id=case_id, title=body.title, body=body.body,
        source_reference=body.source_reference, notes=body.notes,
    )
    from modules.research_engine.services.metadata_service import enrich_and_save
    doc = enrich_and_save(case_id, doc)
    chunks = build_and_save_chunks(case_id, doc)
    summary = rebuild_index(case_id)
    return {
        "document_id": doc.document_id,
        "chunk_count": len(chunks),
        "metadata": doc.meta.model_dump(mode="json"),
        "ingestion_log": log.model_dump(mode="json"),
        "index_summary": summary,
    }


@router.post("/upload")
async def upload_precedent(
    case_id: int,
    notes: Optional[str] = Form(None),
    file: UploadFile = File(...),
    uid: int = Depends(require_profile),
) -> dict:
    _ensure_case(case_id, uid)
    if not file.filename:
        raise DomainError("upload_failed", "Missing filename.", status_code=400)
    pdf_bytes = await file.read()
    duplicate = filename_already_present(case_id, file.filename)
    try:
        doc, log = ingest_pdf(
            case_id=case_id, filename=file.filename,
            pdf_bytes=pdf_bytes, notes=notes,
        )
    except IngestionError as e:
        raise DomainError("ingest_failed", str(e), status_code=400)
    # Metadata enrichment is best-effort. Chunking + indexing too.
    doc = enrich_and_save(case_id, doc)
    chunks = build_and_save_chunks(case_id, doc)
    summary = rebuild_index(case_id)
    return {
        "document_id": doc.document_id,
        "duplicate_filename_warning": duplicate,
        "chunk_count": len(chunks),
        "metadata": doc.meta.model_dump(mode="json"),
        "ingestion_log": log.model_dump(mode="json"),
        "index_summary": summary,
    }


@router.get("/documents/{document_id}")
def get_precedent(case_id: int, document_id: str,
                  uid: int = Depends(require_profile)) -> dict:
    _ensure_case(case_id, uid)
    doc = load_document(case_id, document_id)
    if not doc:
        raise DomainError("document_not_found",
                          "Precedent document not found.", status_code=404)
    return doc.model_dump(mode="json")


@router.delete("/documents/{document_id}")
def delete_precedent(case_id: int, document_id: str,
                     uid: int = Depends(require_profile)) -> dict:
    _ensure_case(case_id, uid)
    if not delete_document(case_id, document_id):
        raise DomainError("document_not_found",
                          "Precedent document not found.", status_code=404)
    rebuild_index(case_id)
    return {"ok": True, "document_id": document_id}


@router.post("/documents/{document_id}/enrich")
def post_enrich(case_id: int, document_id: str,
                uid: int = Depends(require_profile)) -> dict:
    _ensure_case(case_id, uid)
    doc = load_document(case_id, document_id)
    if not doc:
        raise DomainError("document_not_found",
                          "Precedent document not found.", status_code=404)
    doc = enrich_and_save(case_id, doc)
    build_and_save_chunks(case_id, doc)
    rebuild_index(case_id)
    return {"ok": True, "metadata": doc.meta.model_dump(mode="json")}


@router.get("/documents/{document_id}/similar")
def get_similar_documents(case_id: int, document_id: str,
                          top_k: int = 10,
                          uid: int = Depends(require_profile)) -> dict:
    """Find precedents similar to the given one. Uses the doc's most
    informative chunks (headnote / ratio / holding) as a synthetic query
    against the standard retrieval + reranking pipeline."""
    _ensure_case(case_id, uid)
    if not load_document(case_id, document_id):
        raise DomainError("document_not_found",
                          "Precedent document not found.", status_code=404)
    ranked = find_similar(case_id, document_id, top_k=top_k)
    return {
        "seed_document_id": document_id,
        "results": [r.model_dump(mode="json") for r in ranked],
    }


@router.post("/index/rebuild")
def post_rebuild_index(case_id: int,
                       uid: int = Depends(require_profile)) -> dict:
    _ensure_case(case_id, uid)
    return rebuild_index(case_id)


@router.get("/metadata")
def get_metadata_index(case_id: int,
                       uid: int = Depends(require_profile)) -> list[dict]:
    _ensure_case(case_id, uid)
    return load_metadata_index(case_id)


@router.get("/lookup/citation")
def get_lookup_by_citation(case_id: int, citation: str,
                           uid: int = Depends(require_profile)) -> dict:
    """Resolve a citation string to one or more precedents in the corpus.
    Matching is case-insensitive substring; multiple matches are returned
    sorted by date descending."""
    _ensure_case(case_id, uid)
    needle = (citation or "").strip().lower()
    if not needle:
        raise DomainError("empty_citation",
                          "Provide a non-empty citation query.",
                          status_code=400)
    matches = []
    for d in load_metadata_index(case_id):
        haystack = " ".join([
            d.get("citation", ""), d.get("title", ""),
        ]).lower()
        if needle in haystack:
            matches.append(d)
    matches.sort(key=lambda d: d.get("date_decided") or "", reverse=True)
    return {"citation_query": citation, "matches": matches}


# ---------- Research ----------

@router.post("/search")
def post_search(case_id: int, body: SearchBody,
                uid: int = Depends(require_profile)) -> dict:
    _ensure_case(case_id, uid)
    query = _query_from_body(body)
    hits = search(case_id, query)
    ranked = rerank(case_id, query, hits)
    return {
        "query": query.model_dump(mode="json"),
        "hits_retrieved": len(hits),
        "ranked": [r.model_dump(mode="json") for r in ranked],
    }


@router.post("/research")
def post_research(case_id: int, body: SearchBody,
                  uid: int = Depends(require_profile)) -> dict:
    """Full pipeline: retrieve → rerank → synthesise. The caller decides
    whether to persist the session by POST /sessions with the returned
    payload."""
    _ensure_case(case_id, uid)
    query = _query_from_body(body)
    hits = search(case_id, query)
    ranked = rerank(case_id, query, hits)
    answer = synthesize(case_id, query, ranked)
    return {
        "query": query.model_dump(mode="json"),
        "answer": answer.model_dump(mode="json"),
        "ranked": [r.model_dump(mode="json") for r in ranked],
    }


# ---------- Sessions ----------

@router.get("/sessions")
def get_sessions(case_id: int,
                 uid: int = Depends(require_profile)) -> list[dict]:
    _ensure_case(case_id, uid)
    return [s.model_dump(mode="json") for s in list_sessions(case_id)]


@router.get("/sessions/{session_id}")
def get_session(case_id: int, session_id: str,
                uid: int = Depends(require_profile)) -> dict:
    _ensure_case(case_id, uid)
    s = load_session(case_id, session_id)
    if not s:
        raise DomainError("session_not_found",
                          "Research session not found.", status_code=404)
    return s.model_dump(mode="json")


@router.post("/sessions")
def post_session(case_id: int, body: SaveSessionBody,
                 uid: int = Depends(require_profile)) -> dict:
    _ensure_case(case_id, uid)
    # Round-trip the raw dicts through Pydantic for validation.
    from modules.research_engine.schemas.answer_schema import ResearchAnswer
    from modules.research_engine.schemas.retrieval_schema import RankedHit
    try:
        answer = ResearchAnswer.model_validate(body.answer)
        ranked = [RankedHit.model_validate(r) for r in body.ranked_hits]
    except Exception as e:
        raise DomainError("bad_payload", f"Invalid session payload: {e}",
                          status_code=400)
    query = ResearchQuery(query_text=body.query_text,
                          query_type=body.query_type)  # type: ignore[arg-type]
    sess = build_session(
        case_id, query, answer, ranked,
        user_notes=body.user_notes,
        pinned_document_ids=body.pinned_document_ids,
        unresolved_questions=body.unresolved_questions,
    )
    save_session(case_id, sess)
    return {"ok": True, "session_id": sess.session_id}


@router.patch("/sessions/{session_id}/feedback")
def patch_session_feedback(case_id: int, session_id: str, body: FeedbackBody,
                           uid: int = Depends(require_profile)) -> dict:
    """Update feedback fields on a saved session. Any field set to null
    is left untouched."""
    _ensure_case(case_id, uid)
    try:
        sess = update_session_feedback(
            case_id, session_id,
            pinned_document_ids=body.pinned_document_ids,
            user_feedback=body.user_feedback,
            unresolved_questions=body.unresolved_questions,
            user_notes=body.user_notes,
        )
    except ValueError as e:
        raise DomainError("bad_feedback", str(e), status_code=400)
    if not sess:
        raise DomainError("session_not_found",
                          "Research session not found.", status_code=404)
    return {"ok": True, "session": sess.model_dump(mode="json")}


@router.get("/sessions/{session_id}/export/{fmt}")
def get_session_export(case_id: int, session_id: str, fmt: str,
                       uid: int = Depends(require_profile)) -> Response:
    _ensure_case(case_id, uid)
    s = load_session(case_id, session_id)
    if not s:
        raise DomainError("session_not_found",
                          "Research session not found.", status_code=404)
    if fmt == "json":
        return Response(
            content=export_session_json(s),
            media_type="application/json",
            headers={"Content-Disposition":
                     f'attachment; filename="research-{session_id}.json"'},
        )
    if fmt in ("md", "markdown"):
        return Response(
            content=export_session_markdown(s),
            media_type="text/markdown",
            headers={"Content-Disposition":
                     f'attachment; filename="research-{session_id}.md"'},
        )
    if fmt == "pdf":
        pdf_bytes = export_session_pdf(s)
        if not pdf_bytes:
            raise DomainError("pdf_disabled",
                              "PDF export is unavailable (reportlab not "
                              "installed).", status_code=503)
        return Response(
            content=pdf_bytes, media_type="application/pdf",
            headers={"Content-Disposition":
                     f'attachment; filename="research-{session_id}.pdf"'},
        )
    raise DomainError("bad_format",
                      f"Unknown export format: {fmt!r}. Use json | markdown | pdf.",
                      status_code=400)


# ---------- Downstream ----------

@router.post("/downstream/build")
def post_build_downstream(case_id: int,
                          uid: int = Depends(require_profile)) -> dict:
    _ensure_case(case_id, uid)
    payload = build_downstream(case_id)
    return payload.model_dump(mode="json")


@router.get("/downstream")
def get_downstream(case_id: int,
                   uid: int = Depends(require_profile)) -> dict:
    _ensure_case(case_id, uid)
    payload = load_downstream(case_id)
    if not payload:
        raise DomainError("downstream_not_built",
                          "Call POST /downstream/build first.",
                          status_code=409)
    return payload.model_dump(mode="json")
