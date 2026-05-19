"""Disk persistence: folder layout, raw PDFs, canonical JSON, per-doc logs.

The persistence root is `<project_root>/cases/<case_id>/evidence/`.
Files are the source of truth — no DB rows for evidence in this phase.
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from loguru import logger

from config.settings import SETTINGS
from modules.evidence_vault.schemas.evidence_schema import (
    CanonicalEvidence, ExtractionLog,
)
from modules.evidence_vault.utils.file_utils import ensure_dir


# ---------- Path helpers ----------

def cases_root() -> Path:
    """The on-disk root for every per-case workspace. Comes from
    SETTINGS.cases_root, which is driven by the CASES_ROOT env var so
    Render can point it at a mounted persistent disk (e.g. /var/data)."""
    return ensure_dir(SETTINGS.cases_root)


def case_evidence_root(case_id: int | str) -> Path:
    root = cases_root() / str(case_id) / "evidence"
    return root


SUBDIRS = ("raw", "extracted", "chunks", "entities", "reports", "logs")


def ensure_case_dirs(case_id: int | str) -> Path:
    """Create the full evidence/* subtree for a case. Idempotent."""
    root = case_evidence_root(case_id)
    for sub in SUBDIRS:
        (root / sub).mkdir(parents=True, exist_ok=True)
    return root


def raw_pdf_path(case_id: int | str, document_id: str, sanitised_filename: str) -> Path:
    return case_evidence_root(case_id) / "raw" / f"{document_id}__{sanitised_filename}"


def extracted_json_path(case_id: int | str, document_id: str) -> Path:
    return case_evidence_root(case_id) / "extracted" / f"{document_id}.json"


def log_json_path(case_id: int | str, document_id: str) -> Path:
    return case_evidence_root(case_id) / "logs" / f"{document_id}_log.json"


# ---------- Save / load ----------

def save_raw_pdf(case_id: int | str, document_id: str, sanitised_filename: str,
                 pdf_bytes: bytes) -> Path:
    ensure_case_dirs(case_id)
    p = raw_pdf_path(case_id, document_id, sanitised_filename)
    p.write_bytes(pdf_bytes)
    logger.bind(scope="evidence.persistence").info(
        "Saved raw PDF: {} ({} bytes)", p, len(pdf_bytes),
    )
    return p


def save_canonical(case_id: int | str, doc: CanonicalEvidence) -> Path:
    ensure_case_dirs(case_id)
    p = extracted_json_path(case_id, doc.document.document_id)
    p.write_text(doc.model_dump_json(indent=2), encoding="utf-8")
    logger.bind(scope="evidence.persistence").info(
        "Saved canonical JSON: {}", p,
    )
    return p


def load_canonical(case_id: int | str, document_id: str) -> Optional[CanonicalEvidence]:
    p = extracted_json_path(case_id, document_id)
    if not p.exists():
        return None
    return CanonicalEvidence.model_validate_json(p.read_text(encoding="utf-8"))


def save_extraction_log(case_id: int | str, log: ExtractionLog) -> Path:
    ensure_case_dirs(case_id)
    p = log_json_path(case_id, log.document_id)
    p.write_text(log.model_dump_json(indent=2), encoding="utf-8")
    logger.bind(scope="evidence.persistence").info(
        "Saved extraction log: {}", p,
    )
    return p


def load_extraction_log(case_id: int | str, document_id: str) -> Optional[ExtractionLog]:
    p = log_json_path(case_id, document_id)
    if not p.exists():
        return None
    return ExtractionLog.model_validate_json(p.read_text(encoding="utf-8"))


def list_documents(case_id: int | str) -> List[str]:
    """Return document_ids stored for this case, newest first."""
    folder = case_evidence_root(case_id) / "extracted"
    if not folder.exists():
        return []
    files = sorted(folder.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    return [p.stem for p in files]


def iter_documents_for_case_or_none(case_id: int | str):
    """Yield each canonical document as a dict (or None on parse failure).
    Used by the final-report orchestrator which needs the full payload."""
    import json as _json
    folder = case_evidence_root(case_id) / "extracted"
    if not folder.exists():
        return
    for p in sorted(folder.glob("*.json")):
        try:
            yield _json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            yield None


def filename_exists(case_id: int | str, filename: str) -> bool:
    """Used by the upload tab to warn on potential duplicates."""
    folder = case_evidence_root(case_id) / "raw"
    if not folder.exists():
        return False
    target = filename.lower()
    for p in folder.iterdir():
        if p.is_file() and p.name.lower().endswith("__" + target):
            return True
    return False
