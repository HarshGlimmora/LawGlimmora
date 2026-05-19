"""Upload orchestrator: validates, calls extraction, persists everything.

This is the single entry point the UI calls after a successful file pick.
"""
from __future__ import annotations

import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional

from loguru import logger

from config.settings import SETTINGS
from core.db import session_scope, write_audit
from modules.evidence_vault.schemas.evidence_schema import (
    EVIDENCE_DOC_TYPES, CanonicalEvidence, ExtractionLog, LogStep,
)
from modules.evidence_vault.services.chunk_persistence_service import (
    save_per_doc, write_case_aggregates,
)
from modules.evidence_vault.services.chunking_service import run_chunking
from modules.evidence_vault.services.entity_extraction_service import (
    run_entity_extraction,
)
from modules.evidence_vault.services.entity_partition_service import (
    partition_entities,
)
from modules.evidence_vault.services.extraction_service import build_canonical
from modules.evidence_vault.services.persistence_service import (
    ensure_case_dirs, filename_exists, save_canonical, save_extraction_log,
    save_raw_pdf,
)
from modules.evidence_vault.utils.file_utils import (
    new_document_id, sanitise_filename,
)


MAX_PDF_BYTES = 25 * 1024 * 1024  # 25 MB placeholder cap

_LOG_FILE = SETTINGS.root_dir / "modules" / "evidence_vault" / "logs" / "extraction.log"
_extraction_sink_id: Optional[int] = None


def _configure_extraction_sink() -> None:
    """Attach a dedicated loguru sink for the evidence pipeline. Idempotent."""
    global _extraction_sink_id
    if _extraction_sink_id is not None:
        return
    _LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    _extraction_sink_id = logger.add(
        _LOG_FILE,
        rotation="2 MB", retention=5, encoding="utf-8",
        format=("{time:YYYY-MM-DD HH:mm:ss} | {level: <7} | {extra[scope]} | "
                "{message}"),
        filter=lambda record: record["extra"].get("scope", "").startswith("evidence."),
    )


class UploadError(Exception):
    pass


@dataclass
class UploadResult:
    document_id: str
    canonical: CanonicalEvidence
    extraction_log: ExtractionLog
    raw_pdf_path: Path
    canonical_path: Path
    log_path: Path
    duplicate_filename_warning: bool
    # Phase-2 additions
    chunk_count: int = 0
    entity_count: int = 0
    entity_source: str = "regex"     # "vertex" | "aistudio" | "regex"
    partition_summary: dict | None = None
    aggregate_paths: dict | None = None


def _validate(pdf_bytes: bytes, filename: str, doc_type: str) -> None:
    if not pdf_bytes:
        raise UploadError("Empty file.")
    if len(pdf_bytes) > MAX_PDF_BYTES:
        raise UploadError(
            f"File too large ({len(pdf_bytes)/1_048_576:.1f} MB). "
            f"Limit is {MAX_PDF_BYTES/1_048_576:.0f} MB."
        )
    if not filename.lower().endswith(".pdf"):
        raise UploadError("Only PDF files are accepted.")
    if pdf_bytes[:4] != b"%PDF":
        raise UploadError("File does not look like a valid PDF.")
    if doc_type not in EVIDENCE_DOC_TYPES:
        raise UploadError(f"Unknown evidence type: {doc_type!r}.")


def ingest(
    *,
    user_id: int,
    case_id: int,
    pdf_bytes: bytes,
    filename: str,
    evidence_title: str,
    doc_type: str,
    notes: Optional[str] = None,
) -> UploadResult:
    _configure_extraction_sink()
    bound = logger.bind(scope="evidence.upload")

    _validate(pdf_bytes, filename, doc_type)
    ensure_case_dirs(case_id)
    safe_name = sanitise_filename(filename)
    duplicate = filename_exists(case_id, safe_name)
    document_id = new_document_id()
    bound.info("Ingest start: case={} doc={} file={} dup={}",
               case_id, document_id, safe_name, duplicate)

    # Step 4 — save raw PDF
    raw_path = save_raw_pdf(case_id, document_id, safe_name, pdf_bytes)

    # Steps 5-8 — extract, clean, citations, canonical JSON
    canonical, extraction_log = build_canonical(
        document_id=document_id,
        case_id=case_id,
        filename=safe_name,
        evidence_title=evidence_title,
        doc_type=doc_type,
        pdf_bytes=pdf_bytes,
        notes=notes,
    )

    # Step 9 — persist canonical JSON (chunks/entities still empty)
    canonical_path = save_canonical(case_id, canonical)
    extraction_log.steps.append(LogStep(
        name="persist_canonical", status="ok",
        at=datetime.utcnow(),
        detail=str(canonical_path.relative_to(SETTINGS.root_dir)),
    ))

    # Phase-2 chain (only when extraction itself succeeded).
    chunk_count = 0
    entity_count = 0
    entity_source = "regex"
    partition_summary: dict = {}
    aggregate_paths: dict = {}

    if canonical.document.processing_status == "completed":
        # Steps 11-12 — structural segmentation + size normalization
        try:
            chunks = run_chunking(canonical)
            chunk_count = len(chunks)
            extraction_log.steps.append(LogStep(
                name="structural_segmentation", status="ok",
                at=datetime.utcnow(),
                detail=f"hybrid chunking produced {chunk_count} chunk(s)",
            ))
            extraction_log.steps.append(LogStep(
                name="chunk_citation_anchoring", status="ok",
                at=datetime.utcnow(),
                detail=f"{chunk_count} chunk-level citation anchor(s) created",
            ))
        except Exception as exc:
            bound.exception("Chunking failed")
            chunks = []
            extraction_log.steps.append(LogStep(
                name="structural_segmentation", status="error",
                at=datetime.utcnow(), detail=str(exc),
            ))

        # Steps 13-14 — entity extraction + normalization
        entities = []
        chunk_back_refs: dict[str, list[str]] = {}
        if chunks:
            try:
                entities, chunk_back_refs, entity_source = run_entity_extraction(
                    document_id=document_id, chunks=chunks,
                )
                entity_count = len(entities)
                extraction_log.steps.append(LogStep(
                    name="entity_extraction", status="ok",
                    at=datetime.utcnow(),
                    detail=f"{entity_count} entity(ies) via {entity_source}",
                ))
                extraction_log.steps.append(LogStep(
                    name="entity_normalization", status="ok",
                    at=datetime.utcnow(),
                    detail="ISO dates, numeric amounts, canonical sections/clauses",
                ))
            except Exception as exc:
                bound.exception("Entity extraction failed")
                extraction_log.steps.append(LogStep(
                    name="entity_extraction", status="error",
                    at=datetime.utcnow(), detail=str(exc),
                ))

        # Attach entity_ids back onto each chunk
        for c in chunks:
            c.entities = chunk_back_refs.get(c.chunk_id, [])

        # Step 15 — partitioning
        partitions = []
        try:
            partitions = partition_entities(entities)
            partition_summary = {p.partition_type: len(p.entities) for p in partitions}
            extraction_log.steps.append(LogStep(
                name="entity_partitioning", status="ok",
                at=datetime.utcnow(),
                detail=" ".join(f"{k}={v}" for k, v in partition_summary.items()),
            ))
        except Exception as exc:
            bound.exception("Partitioning failed")
            extraction_log.steps.append(LogStep(
                name="entity_partitioning", status="error",
                at=datetime.utcnow(), detail=str(exc),
            ))

        # Embed chunks + entities into the canonical JSON in place
        canonical.chunks = [c.model_dump(mode="json") for c in chunks]
        canonical.entities = [e.model_dump(mode="json") for e in entities]
        save_canonical(case_id, canonical)  # second write — now with chunks+entities

        # Step 16 — persist case-level aggregates
        try:
            save_per_doc(case_id, document_id, chunks, entities)
            aggregate_paths = {
                k: str(v.relative_to(SETTINGS.root_dir))
                for k, v in write_case_aggregates(case_id, partitions).items()
            }
            extraction_log.steps.append(LogStep(
                name="persist_chunks_entities", status="ok",
                at=datetime.utcnow(),
                detail=("chunks.json + entities.json + partitions.json"
                        if chunks else "no chunks to persist"),
            ))
        except Exception as exc:
            bound.exception("Case aggregate write failed")
            extraction_log.steps.append(LogStep(
                name="persist_chunks_entities", status="error",
                at=datetime.utcnow(), detail=str(exc),
            ))
    else:
        bound.warning("Skipping Phase-2 chain for {} (extraction status={})",
                      document_id, canonical.document.processing_status)

    # Persist the final, fully-populated log
    log_path = save_extraction_log(case_id, extraction_log)
    bound.info(
        "Ingest done: doc={} pages={} ms={} status={} chunks={} entities={} source={}",
        document_id, canonical.document.page_count,
        canonical.summary.extraction_duration_ms,
        canonical.document.processing_status,
        chunk_count, entity_count, entity_source,
    )

    with session_scope() as sess:
        write_audit(
            sess, user_id=user_id, action="evidence.upload",
            target_type="case", target_id=case_id,
            message=(f"{document_id} · {canonical.document.evidence_title} "
                     f"({doc_type}, {canonical.document.page_count}p, "
                     f"chunks={chunk_count}, entities={entity_count}, "
                     f"source={entity_source})"),
        )

    return UploadResult(
        document_id=document_id,
        canonical=canonical,
        extraction_log=extraction_log,
        raw_pdf_path=raw_path,
        canonical_path=canonical_path,
        log_path=log_path,
        duplicate_filename_warning=duplicate,
        chunk_count=chunk_count,
        entity_count=entity_count,
        entity_source=entity_source,
        partition_summary=partition_summary or None,
        aggregate_paths=aggregate_paths or None,
    )
