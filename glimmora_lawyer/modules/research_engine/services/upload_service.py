"""PDF intake: validate, extract pages with PyMuPDF, build PrecedentDocument.

This service is *only* responsible for getting bytes onto disk and producing
the first canonical PrecedentDocument with empty PrecedentMeta. Metadata
enrichment and chunking are subsequent steps owned by their own services.
"""
from __future__ import annotations

import time
from datetime import datetime
from typing import List, Tuple

import fitz  # PyMuPDF
from loguru import logger

from modules.research_engine.schemas.corpus_schema import (
    IngestionLog, IngestionLogStep, PrecedentDocument, PrecedentMeta,
    PrecedentPage,
)
from modules.research_engine.services.persistence_service import (
    save_document, save_ingestion_log, save_raw_pdf,
)
# Reuse Package 1's filename hygiene + id helpers — they're domain-neutral.
from modules.evidence_vault.utils.file_utils import (
    new_document_id, sanitise_filename,
)


log = logger.bind(scope="research.upload")


class IngestionError(Exception):
    pass


def _step(name: str, status: str, detail: str | None = None) -> IngestionLogStep:
    return IngestionLogStep(name=name, status=status,  # type: ignore[arg-type]
                            at=datetime.utcnow(), detail=detail)


def _extract_pages(pdf_bytes: bytes) -> List[str]:
    if not pdf_bytes or pdf_bytes[:4] != b"%PDF":
        raise IngestionError("Not a valid PDF (missing %PDF header).")
    pages: List[str] = []
    try:
        with fitz.open(stream=pdf_bytes, filetype="pdf") as pdf:
            for page in pdf:
                try:
                    txt = page.get_text("text") or ""
                except Exception as exc:
                    log.warning("Page {} extract failed: {}", page.number + 1, exc)
                    txt = ""
                pages.append(txt)
    except fitz.FileDataError as exc:
        raise IngestionError(f"Corrupt or unreadable PDF: {exc}") from exc
    except Exception as exc:
        raise IngestionError(f"PDF could not be opened: {exc}") from exc
    return pages


def ingest_pdf(
    *,
    case_id: int | str,
    filename: str,
    pdf_bytes: bytes,
    notes: str | None = None,
) -> Tuple[PrecedentDocument, IngestionLog]:
    """Persist the raw PDF, extract pages, and return a first-pass document.

    Status after this call is "extracted". metadata_service brings it to
    "enriched", and indexing_service brings it to "indexed".
    """
    document_id = new_document_id()
    safe_name = sanitise_filename(filename)
    started = datetime.utcnow()
    t0 = time.perf_counter()
    steps: List[IngestionLogStep] = [_step("pdf_received", "ok",
                                           f"{len(pdf_bytes)} bytes filename={safe_name}")]

    # Persist raw bytes first so we never lose the source.
    save_raw_pdf(case_id, document_id, safe_name, pdf_bytes)
    steps.append(_step("raw_pdf_saved", "ok", f"document_id={document_id}"))

    try:
        page_texts = _extract_pages(pdf_bytes)
        steps.append(_step("page_extraction", "ok",
                           f"extracted {len(page_texts)} page(s)"))
    except IngestionError as exc:
        steps.append(_step("page_extraction", "error", str(exc)))
        return _failed_doc(document_id, case_id, safe_name, notes,
                           started, t0, steps, str(exc))

    pages = [PrecedentPage(page_number=i + 1, text=t)
             for i, t in enumerate(page_texts)]
    full_text = "\n\n".join(p.text for p in pages).strip()

    meta = PrecedentMeta(
        document_id=document_id,
        title=safe_name.rsplit(".", 1)[0],   # placeholder until metadata pass
        source_type="pdf_upload",
        source_reference=safe_name,
    )
    doc = PrecedentDocument(
        document_id=document_id,
        case_id=str(case_id),
        filename=safe_name,
        ingested_at=started,
        page_count=len(pages),
        full_text=full_text,
        pages=pages,
        meta=meta,
        status="extracted",
        notes=(notes or "").strip() or None,
    )

    save_document(case_id, doc)
    steps.append(_step("canonical_saved", "ok",
                       f"pages={doc.page_count} chars={len(full_text)}"))

    duration = int((time.perf_counter() - t0) * 1000)
    ingestion_log = IngestionLog(
        document_id=document_id, case_id=str(case_id), filename=safe_name,
        started_at=started, ended_at=datetime.utcnow(),
        duration_ms=duration, result="completed", steps=steps,
    )
    save_ingestion_log(case_id, ingestion_log)
    log.info("Ingested precedent: doc={} pages={} ms={}",
             document_id, doc.page_count, duration)
    return doc, ingestion_log


def ingest_text(
    *,
    case_id: int | str,
    title: str,
    body: str,
    source_reference: str = "",
    notes: str | None = None,
) -> Tuple[PrecedentDocument, IngestionLog]:
    """Same end-state as `ingest_pdf` but for raw text (e.g. reporter dump,
    pasted judgment). One synthetic page is built so the chunking pipeline
    treats it the same as a real PDF."""
    document_id = new_document_id()
    safe_name = sanitise_filename(f"{title or 'precedent'}.txt")
    started = datetime.utcnow()
    t0 = time.perf_counter()
    steps: List[IngestionLogStep] = [
        _step("text_received", "ok", f"{len(body)} chars title={title!r}"),
    ]

    pages = [PrecedentPage(page_number=1, text=body or "")]
    meta = PrecedentMeta(
        document_id=document_id,
        title=title or "(untitled)",
        source_type="plain_text",
        source_reference=source_reference or safe_name,
    )
    doc = PrecedentDocument(
        document_id=document_id,
        case_id=str(case_id),
        filename=safe_name,
        ingested_at=started,
        page_count=1,
        full_text=body or "",
        pages=pages,
        meta=meta,
        status="extracted",
        notes=(notes or "").strip() or None,
    )
    save_document(case_id, doc)
    steps.append(_step("canonical_saved", "ok",
                       f"chars={len(body or '')}"))

    duration = int((time.perf_counter() - t0) * 1000)
    ingestion_log = IngestionLog(
        document_id=document_id, case_id=str(case_id), filename=safe_name,
        started_at=started, ended_at=datetime.utcnow(),
        duration_ms=duration, result="completed", steps=steps,
    )
    save_ingestion_log(case_id, ingestion_log)
    log.info("Ingested precedent (text): doc={} chars={} ms={}",
             document_id, len(body or ""), duration)
    return doc, ingestion_log


def _failed_doc(document_id: str, case_id: int | str, filename: str,
                notes: str | None, started: datetime, t0: float,
                steps: List[IngestionLogStep],
                err: str) -> Tuple[PrecedentDocument, IngestionLog]:
    meta = PrecedentMeta(document_id=document_id, title=filename)
    doc = PrecedentDocument(
        document_id=document_id, case_id=str(case_id), filename=filename,
        ingested_at=started, page_count=0, full_text="", pages=[],
        meta=meta, status="failed", notes=(notes or "").strip() or None,
    )
    save_document(case_id, doc)
    duration = int((time.perf_counter() - t0) * 1000)
    ingestion_log = IngestionLog(
        document_id=document_id, case_id=str(case_id), filename=filename,
        started_at=started, ended_at=datetime.utcnow(),
        duration_ms=duration, result="failed", steps=steps, error=err,
    )
    save_ingestion_log(case_id, ingestion_log)
    return doc, ingestion_log
