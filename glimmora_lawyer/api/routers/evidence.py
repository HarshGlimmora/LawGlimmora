"""Evidence vault routes — upload + read."""
from __future__ import annotations

import json
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, UploadFile

from api.deps import require_profile
from api.errors import DomainError
from modules.case.services.case_service import get_case
from modules.evidence_vault.services.chunk_persistence_service import (
    load_case_chunks, load_case_entities, load_case_partitions,
)
from modules.evidence_vault.services.persistence_service import (
    case_evidence_root, list_documents, load_canonical, load_extraction_log,
)
from modules.evidence_vault.services.retrieval_service import (
    build_retrieval_index_if_missing, retrieve,
)
from modules.evidence_vault.services.upload_service import UploadError, ingest

router = APIRouter(prefix="/api/cases/{case_id}/evidence", tags=["evidence"])


def _ensure_case(case_id: int, uid: int) -> None:
    if not get_case(uid, case_id):
        raise DomainError("case_not_found", "Case not found.", status_code=404)


@router.get("/documents")
def list_evidence_documents(case_id: int, uid: int = Depends(require_profile)) -> list[dict]:
    """Hydrate each stored document_id into the summary fields the frontend
    needs. `persistence_service.list_documents` only returns the ids — we
    load the canonical JSON to expose filename, title, page count, status."""
    _ensure_case(case_id, uid)
    summaries: list[dict] = []
    for doc_id in list_documents(case_id):
        doc = load_canonical(case_id, doc_id)
        if not doc:
            continue
        m = doc.document
        summaries.append({
            "document_id": m.document_id,
            "filename": m.filename,
            "evidence_title": m.evidence_title,
            "doc_type": m.doc_type,
            "uploaded_at": m.uploaded_at.isoformat(),
            "page_count": m.page_count,
            "processing_status": m.processing_status,
        })
    return summaries


@router.post("/upload")
async def upload_evidence(
    case_id: int,
    evidence_title: str = Form(...),
    doc_type: str = Form(...),
    notes: Optional[str] = Form(None),
    file: UploadFile = File(...),
    uid: int = Depends(require_profile),
) -> dict:
    _ensure_case(case_id, uid)
    if not file.filename:
        raise DomainError("upload_failed", "Missing filename.", status_code=400)
    pdf_bytes = await file.read()
    try:
        result = ingest(
            user_id=uid,
            case_id=case_id,
            pdf_bytes=pdf_bytes,
            filename=file.filename,
            evidence_title=evidence_title,
            doc_type=doc_type,
            notes=notes,
        )
    except UploadError as e:
        raise DomainError("upload_failed", str(e), status_code=400)
    return {
        "document_id": result.document_id,
        "duplicate_filename_warning": result.duplicate_filename_warning,
        "chunk_count": result.chunk_count,
        "entity_count": result.entity_count,
        "entity_source": result.entity_source,
        "partition_summary": result.partition_summary,
        "canonical": result.canonical.model_dump(mode="json"),
        "extraction_log": result.extraction_log.model_dump(mode="json"),
    }


@router.get("/documents/{document_id}")
def get_evidence_document(case_id: int, document_id: str,
                          uid: int = Depends(require_profile)) -> dict:
    _ensure_case(case_id, uid)
    doc = load_canonical(case_id, document_id)
    if not doc:
        raise DomainError("document_not_found", "Evidence document not found.", status_code=404)
    return doc.model_dump(mode="json")


@router.get("/documents/{document_id}/log")
def get_evidence_log(case_id: int, document_id: str,
                     uid: int = Depends(require_profile)) -> dict:
    _ensure_case(case_id, uid)
    log = load_extraction_log(case_id, document_id)
    if not log:
        raise DomainError("log_not_found", "Extraction log not found.", status_code=404)
    return log.model_dump(mode="json")


@router.get("/chunks")
def get_case_chunks(case_id: int, uid: int = Depends(require_profile)) -> list[dict]:
    """Returns the flat list of chunks across every document in the case.
    The persisted aggregate is `{case_id, generated_at, total_chunks,
    chunks: [...]}` — we surface the inner list directly so frontends
    iterate over chunk records, not envelope keys."""
    _ensure_case(case_id, uid)
    payload = load_case_chunks(case_id) or {}
    return list(payload.get("chunks") or [])


@router.get("/entities")
def get_case_entities(case_id: int, uid: int = Depends(require_profile)) -> list[dict]:
    _ensure_case(case_id, uid)
    payload = load_case_entities(case_id) or {}
    return list(payload.get("entities") or [])


@router.get("/partitions")
def get_case_partitions(case_id: int, uid: int = Depends(require_profile)) -> list[dict]:
    _ensure_case(case_id, uid)
    payload = load_case_partitions(case_id) or {}
    return list(payload.get("partitions") or [])


def _read_ledger(case_id: int, name: str) -> list[dict]:
    """Read `cases/<id>/evidence/reports/<name>.json` as a list of items.

    These ledgers are written by the FinalReport orchestrator. The file
    schema is {"items": [...]} — we return the inner list (empty when the
    file is missing, so the frontend renders an empty-state instead of
    erroring before the first report has been generated)."""
    p = case_evidence_root(case_id) / "reports" / f"{name}.json"
    if not p.exists():
        return []
    try:
        payload = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return []
    return list(payload.get("items") or [])


@router.get("/contradictions")
def get_contradictions(case_id: int,
                       uid: int = Depends(require_profile)) -> list[dict]:
    _ensure_case(case_id, uid)
    return _read_ledger(case_id, "contradictions")


@router.get("/missing-evidence")
def get_missing_evidence(case_id: int,
                         uid: int = Depends(require_profile)) -> list[dict]:
    _ensure_case(case_id, uid)
    return _read_ledger(case_id, "missing_evidence")


@router.post("/search")
def post_search(case_id: int, body: dict, uid: int = Depends(require_profile)) -> dict:
    _ensure_case(case_id, uid)
    query = (body.get("query") or "").strip()
    if not query:
        raise DomainError("empty_query", "Query is empty.", status_code=400)
    mode = body.get("mode") or "hybrid"
    partition_filter = body.get("partition_filter")
    build_retrieval_index_if_missing(case_id)
    ctx = retrieve(case_id=case_id, query=query, mode=mode,
                   partition_filter=partition_filter)
    return ctx.model_dump(mode="json")
