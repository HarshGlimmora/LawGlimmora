"""PyMuPDF page-by-page text extraction + canonical JSON builder.

Returns a fully populated `CanonicalEvidence` and an `ExtractionLog`.
The orchestration (file save, log save, UI) belongs to `upload_service`.
"""
from __future__ import annotations

import io
import time
from datetime import datetime
from typing import List, Tuple

import fitz  # PyMuPDF
from loguru import logger

from modules.evidence_vault.schemas.evidence_schema import (
    CanonicalEvidence, DocumentMeta, ExtractionLog, ExtractionSummary,
    LogStep, PageRecord,
)
from modules.evidence_vault.services.citation_service import build_page_citation
from modules.evidence_vault.services.cleaning_service import clean_text
from modules.evidence_vault.utils.file_utils import sha256_short
from modules.evidence_vault.utils.text_utils import count_chars, count_words


class ExtractionError(Exception):
    pass


def extract_pages_from_pdf(pdf_bytes: bytes) -> List[str]:
    """Returns one raw-text string per page, in original order."""
    if not pdf_bytes or pdf_bytes[:4] != b"%PDF":
        raise ExtractionError("Not a valid PDF (missing %PDF header).")
    pages: List[str] = []
    try:
        with fitz.open(stream=pdf_bytes, filetype="pdf") as doc:
            for page in doc:
                try:
                    txt = page.get_text("text") or ""
                except Exception as exc:
                    logger.bind(scope="evidence.extraction").warning(
                        "page {} extract failed: {}", page.number + 1, exc,
                    )
                    txt = ""
                pages.append(txt)
    except fitz.FileDataError as exc:
        raise ExtractionError(f"Corrupt or unreadable PDF: {exc}") from exc
    except Exception as exc:
        raise ExtractionError(f"PDF could not be opened: {exc}") from exc
    return pages


def _step(name: str, status: str, detail: str | None = None) -> LogStep:
    return LogStep(name=name, status=status, at=datetime.utcnow(), detail=detail)  # type: ignore[arg-type]


def build_canonical(
    *,
    document_id: str,
    case_id: int | str,
    filename: str,
    evidence_title: str,
    doc_type: str,
    pdf_bytes: bytes,
    notes: str | None = None,
) -> Tuple[CanonicalEvidence, ExtractionLog]:
    """Run extract → clean → canonical-build for one PDF."""
    log_steps: List[LogStep] = [_step("pdf_received", "ok",
                                      f"{len(pdf_bytes)} bytes, filename={filename}")]
    started = datetime.utcnow()
    t0 = time.perf_counter()
    bound = logger.bind(scope="evidence.extraction")
    bound.info("Extraction start: {} ({} bytes)", filename, len(pdf_bytes))

    try:
        raw_pages = extract_pages_from_pdf(pdf_bytes)
        log_steps.append(_step("page_extraction", "ok",
                               f"extracted {len(raw_pages)} page(s)"))
    except ExtractionError as exc:
        log_steps.append(_step("page_extraction", "error", str(exc)))
        bound.error("Page extraction failed: {}", exc)
        return _failed_payload(document_id, case_id, filename, evidence_title,
                               doc_type, notes, started, t0, log_steps, str(exc))

    pages: List[PageRecord] = []
    for i, raw in enumerate(raw_pages, start=1):
        cleaned = clean_text(raw)
        citation = build_page_citation(
            document_id=document_id, filename=filename, page_number=i,
        )
        pages.append(PageRecord(
            page_number=i,
            raw_text=raw,
            clean_text=cleaned,
            page_hash=sha256_short(cleaned) if cleaned else "",
            character_count=count_chars(cleaned),
            word_count=count_words(cleaned),
            citations=[citation],
            entities=[],
            claims=[],
        ))
    log_steps.append(_step("text_cleaning", "ok",
                           f"normalised {len(pages)} page(s)"))
    log_steps.append(_step("citation_anchoring", "ok",
                           f"created {len(pages)} page-level citation(s)"))

    summary = ExtractionSummary(
        total_pages=len(pages),
        total_characters=sum(p.character_count for p in pages),
        total_words=sum(p.word_count for p in pages),
        extraction_duration_ms=int((time.perf_counter() - t0) * 1000),
    )

    meta = DocumentMeta(
        document_id=document_id,
        case_id=str(case_id),
        filename=filename,
        evidence_title=evidence_title.strip() or filename,
        doc_type=doc_type,
        source="user_upload",
        language="en",
        jurisdiction="India",
        uploaded_at=started,
        page_count=len(pages),
        processing_status="completed",
        notes=(notes or "").strip() or None,
    )

    canonical = CanonicalEvidence(
        document=meta, pages=pages, chunks=[], entities=[], claims=[],
        contradictions=[], missing_evidence=[], argument_recommendations=[],
        summary=summary,
    )
    log_steps.append(_step("canonical_json_built", "ok",
                           f"pages={summary.total_pages} words={summary.total_words}"))

    extraction_log = ExtractionLog(
        document_id=document_id,
        case_id=str(case_id),
        filename=filename,
        started_at=started,
        ended_at=datetime.utcnow(),
        duration_ms=summary.extraction_duration_ms,
        page_count=summary.total_pages,
        result="completed",
        steps=log_steps,
    )
    bound.info("Extraction complete: {} doc={} pages={} ms={}",
               filename, document_id, summary.total_pages,
               summary.extraction_duration_ms)
    return canonical, extraction_log


def _failed_payload(
    document_id: str, case_id: int | str, filename: str, evidence_title: str,
    doc_type: str, notes: str | None, started, t0, steps: List[LogStep], err: str,
) -> Tuple[CanonicalEvidence, ExtractionLog]:
    duration_ms = int((time.perf_counter() - t0) * 1000)
    meta = DocumentMeta(
        document_id=document_id, case_id=str(case_id), filename=filename,
        evidence_title=evidence_title.strip() or filename, doc_type=doc_type,
        source="user_upload", language="en", jurisdiction="India",
        uploaded_at=started, page_count=0,
        processing_status="failed", notes=(notes or "").strip() or None,
    )
    canonical = CanonicalEvidence(document=meta)
    canonical.summary = ExtractionSummary(extraction_duration_ms=duration_ms)
    extraction_log = ExtractionLog(
        document_id=document_id, case_id=str(case_id), filename=filename,
        started_at=started, ended_at=datetime.utcnow(),
        duration_ms=duration_ms, page_count=0, result="failed",
        steps=steps, error=err,
    )
    return canonical, extraction_log
