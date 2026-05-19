"""Disk persistence: per-case research folder layout + canonical I/O.

Layout (rooted at <project_root>/cases/<case_id>/research/):

    corpus/raw/<doc_id>__<filename>.pdf
    corpus/extracted/<doc_id>.json   <- PrecedentDocument
    chunks/<doc_id>.json             <- list[PrecedentChunk]
    index/bm25.json                  <- BM25 state for the case
    index/metadata_index.json        <- filterable metadata list
    sessions/<session_id>.json       <- ResearchSession
    outputs/downstream.json          <- DownstreamPayload
    logs/<doc_id>_log.json           <- IngestionLog
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import List, Optional

from loguru import logger

from config.settings import SETTINGS
from modules.research_engine.schemas.corpus_schema import (
    IngestionLog, PrecedentDocument,
)


SUBDIRS = (
    "corpus/raw",
    "corpus/extracted",
    "chunks",
    "index",
    "sessions",
    "outputs",
    "logs",
)


# ---------- Path helpers ----------

def _ensure(p: Path) -> Path:
    p.mkdir(parents=True, exist_ok=True)
    return p


def cases_root() -> Path:
    """Per-case workspace root. Driven by SETTINGS.cases_root (CASES_ROOT
    env) so Render can mount a persistent disk and not lose ingested
    precedent PDFs on every restart."""
    return _ensure(SETTINGS.cases_root)


def case_research_root(case_id: int | str) -> Path:
    return cases_root() / str(case_id) / "research"


def ensure_case_dirs(case_id: int | str) -> Path:
    root = case_research_root(case_id)
    for sub in SUBDIRS:
        (root / sub).mkdir(parents=True, exist_ok=True)
    return root


def raw_pdf_path(case_id: int | str, document_id: str, sanitised_filename: str) -> Path:
    return case_research_root(case_id) / "corpus" / "raw" / f"{document_id}__{sanitised_filename}"


def extracted_json_path(case_id: int | str, document_id: str) -> Path:
    return case_research_root(case_id) / "corpus" / "extracted" / f"{document_id}.json"


def chunks_json_path(case_id: int | str, document_id: str) -> Path:
    return case_research_root(case_id) / "chunks" / f"{document_id}.json"


def log_json_path(case_id: int | str, document_id: str) -> Path:
    return case_research_root(case_id) / "logs" / f"{document_id}_log.json"


def bm25_path(case_id: int | str) -> Path:
    return case_research_root(case_id) / "index" / "bm25.json"


def metadata_index_path(case_id: int | str) -> Path:
    return case_research_root(case_id) / "index" / "metadata_index.json"


def session_path(case_id: int | str, session_id: str) -> Path:
    return case_research_root(case_id) / "sessions" / f"{session_id}.json"


def sessions_dir(case_id: int | str) -> Path:
    return case_research_root(case_id) / "sessions"


def downstream_path(case_id: int | str) -> Path:
    return case_research_root(case_id) / "outputs" / "downstream.json"


# ---------- Save / load ----------

def save_raw_pdf(case_id: int | str, document_id: str, sanitised_filename: str,
                 pdf_bytes: bytes) -> Path:
    ensure_case_dirs(case_id)
    p = raw_pdf_path(case_id, document_id, sanitised_filename)
    p.write_bytes(pdf_bytes)
    logger.bind(scope="research.persistence").info(
        "Saved raw PDF: {} ({} bytes)", p, len(pdf_bytes),
    )
    return p


def save_document(case_id: int | str, doc: PrecedentDocument) -> Path:
    ensure_case_dirs(case_id)
    p = extracted_json_path(case_id, doc.document_id)
    p.write_text(doc.model_dump_json(indent=2), encoding="utf-8")
    logger.bind(scope="research.persistence").info(
        "Saved precedent doc: {}", p,
    )
    return p


def load_document(case_id: int | str, document_id: str) -> Optional[PrecedentDocument]:
    p = extracted_json_path(case_id, document_id)
    if not p.exists():
        return None
    return PrecedentDocument.model_validate_json(p.read_text(encoding="utf-8"))


def save_chunks(case_id: int | str, document_id: str, chunks_payload: dict) -> Path:
    ensure_case_dirs(case_id)
    p = chunks_json_path(case_id, document_id)
    p.write_text(json.dumps(chunks_payload, indent=2, ensure_ascii=False),
                 encoding="utf-8")
    logger.bind(scope="research.persistence").info("Saved chunks: {}", p)
    return p


def load_chunks(case_id: int | str, document_id: str) -> Optional[dict]:
    p = chunks_json_path(case_id, document_id)
    if not p.exists():
        return None
    return json.loads(p.read_text(encoding="utf-8"))


def save_ingestion_log(case_id: int | str, log: IngestionLog) -> Path:
    ensure_case_dirs(case_id)
    p = log_json_path(case_id, log.document_id)
    p.write_text(log.model_dump_json(indent=2), encoding="utf-8")
    logger.bind(scope="research.persistence").info("Saved ingestion log: {}", p)
    return p


def list_documents(case_id: int | str) -> List[str]:
    """Return precedent document_ids for this case, newest first."""
    folder = case_research_root(case_id) / "corpus" / "extracted"
    if not folder.exists():
        return []
    files = sorted(folder.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    return [p.stem for p in files]


def iter_documents(case_id: int | str):
    """Yield each PrecedentDocument as a dict (or skip on parse failure)."""
    folder = case_research_root(case_id) / "corpus" / "extracted"
    if not folder.exists():
        return
    for p in sorted(folder.glob("*.json")):
        try:
            yield json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            continue


def iter_all_chunks(case_id: int | str):
    """Yield every chunk dict across all documents in the case."""
    folder = case_research_root(case_id) / "chunks"
    if not folder.exists():
        return
    for p in sorted(folder.glob("*.json")):
        try:
            payload = json.loads(p.read_text(encoding="utf-8"))
            for c in payload.get("chunks", []):
                yield c
        except Exception:
            continue


def filename_already_present(case_id: int | str, filename: str) -> bool:
    """Used by the upload tab to warn on potential duplicates."""
    folder = case_research_root(case_id) / "corpus" / "raw"
    if not folder.exists():
        return False
    target = filename.lower()
    for p in folder.iterdir():
        if p.is_file() and p.name.lower().endswith("__" + target):
            return True
    return False


def delete_document(case_id: int | str, document_id: str) -> bool:
    """Remove the raw PDF, extracted JSON, chunks JSON, and log for a doc."""
    deleted = False
    p_ext = extracted_json_path(case_id, document_id)
    if p_ext.exists():
        p_ext.unlink()
        deleted = True
    p_ch = chunks_json_path(case_id, document_id)
    if p_ch.exists():
        p_ch.unlink()
        deleted = True
    p_log = log_json_path(case_id, document_id)
    if p_log.exists():
        p_log.unlink()
        deleted = True
    # Raw PDFs share the doc id prefix:
    raw_folder = case_research_root(case_id) / "corpus" / "raw"
    if raw_folder.exists():
        for f in raw_folder.iterdir():
            if f.name.startswith(f"{document_id}__"):
                f.unlink()
                deleted = True
    return deleted
