"""File / path helpers."""
from __future__ import annotations

import hashlib
import re
import uuid
from pathlib import Path


_SAFE_RE = re.compile(r"[^A-Za-z0-9._-]+")


def new_document_id() -> str:
    """Stable doc id used in filenames, JSON, and citations."""
    return "doc-" + uuid.uuid4().hex[:12]


def new_citation_id() -> str:
    return "cit-" + uuid.uuid4().hex[:10]


def sanitise_filename(name: str, max_len: int = 80) -> str:
    """Strip path components and replace anything not URL-safe."""
    base = Path(name).name
    safe = _SAFE_RE.sub("_", base).strip("_")
    if not safe:
        safe = "document.pdf"
    if len(safe) > max_len:
        stem = safe[: max_len - 8]
        ext = Path(safe).suffix
        safe = stem + ext
    return safe


def sha256_short(data: str | bytes, n: int = 16) -> str:
    if isinstance(data, str):
        data = data.encode("utf-8")
    return hashlib.sha256(data).hexdigest()[:n]


def ensure_dir(p: Path) -> Path:
    p.mkdir(parents=True, exist_ok=True)
    return p
