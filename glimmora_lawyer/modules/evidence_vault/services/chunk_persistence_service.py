"""Case-level aggregates for chunks, entities, partitions.

Writes (and re-writes, every ingest) three files under the case folder:

  cases/<case_id>/evidence/chunks/chunks.json
  cases/<case_id>/evidence/entities/entities.json
  cases/<case_id>/evidence/entities/partitions.json

Per-document chunk/entity records also live inside the canonical JSON at
`extracted/<doc_id>.json` (populated in place by upload_service).
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from loguru import logger

from modules.evidence_vault.schemas.chunk_schema import ChunkRecord
from modules.evidence_vault.schemas.entity_schema import (
    EntityRecord, Partition,
)
from modules.evidence_vault.services.persistence_service import (
    case_evidence_root, ensure_case_dirs,
)


def chunks_root(case_id: int | str) -> Path:
    return case_evidence_root(case_id) / "chunks"


def entities_root(case_id: int | str) -> Path:
    return case_evidence_root(case_id) / "entities"


def chunks_index_path(case_id: int | str) -> Path:
    return chunks_root(case_id) / "chunks.json"


def entities_index_path(case_id: int | str) -> Path:
    return entities_root(case_id) / "entities.json"


def partitions_index_path(case_id: int | str) -> Path:
    return entities_root(case_id) / "partitions.json"


# ---------- Per-document files (for debugging convenience) ----------

def per_doc_chunks_path(case_id: int | str, document_id: str) -> Path:
    return chunks_root(case_id) / f"{document_id}.json"


def per_doc_entities_path(case_id: int | str, document_id: str) -> Path:
    return entities_root(case_id) / f"{document_id}.json"


def save_per_doc(case_id: int | str, document_id: str,
                 chunks: List[ChunkRecord],
                 entities: List[EntityRecord]) -> None:
    ensure_case_dirs(case_id)
    per_doc_chunks_path(case_id, document_id).write_text(
        json.dumps([c.model_dump(mode="json") for c in chunks], indent=2),
        encoding="utf-8",
    )
    per_doc_entities_path(case_id, document_id).write_text(
        json.dumps([e.model_dump(mode="json") for e in entities], indent=2),
        encoding="utf-8",
    )


# ---------- Case-level aggregate writers ----------

def _collect_per_doc_chunks(case_id: int | str) -> List[Dict]:
    folder = chunks_root(case_id)
    if not folder.exists():
        return []
    out: List[Dict] = []
    for p in sorted(folder.glob("*.json")):
        if p.name == "chunks.json":
            continue
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
            if isinstance(data, list):
                out.extend(data)
        except Exception as exc:
            logger.bind(scope="evidence.persistence").warning(
                "Skipping malformed per-doc chunks file {}: {}", p.name, exc,
            )
    return out


def _collect_per_doc_entities(case_id: int | str) -> List[Dict]:
    folder = entities_root(case_id)
    if not folder.exists():
        return []
    out: List[Dict] = []
    for p in sorted(folder.glob("*.json")):
        if p.name in {"entities.json", "partitions.json"}:
            continue
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
            if isinstance(data, list):
                out.extend(data)
        except Exception as exc:
            logger.bind(scope="evidence.persistence").warning(
                "Skipping malformed per-doc entities file {}: {}", p.name, exc,
            )
    return out


def write_case_aggregates(case_id: int | str,
                          partitions: Optional[List[Partition]] = None) -> Dict[str, Path]:
    """Rebuild case-level chunks.json, entities.json, partitions.json from
    per-doc files. If `partitions` is provided it's used directly; otherwise
    partitions.json is rebuilt from the collected entities."""
    ensure_case_dirs(case_id)

    all_chunks = _collect_per_doc_chunks(case_id)
    all_entities = _collect_per_doc_entities(case_id)

    chunks_payload = {
        "case_id": str(case_id),
        "generated_at": datetime.utcnow().isoformat(timespec="seconds"),
        "total_chunks": len(all_chunks),
        "chunks": all_chunks,
    }
    entities_payload = {
        "case_id": str(case_id),
        "generated_at": datetime.utcnow().isoformat(timespec="seconds"),
        "total_entities": len(all_entities),
        "entities": all_entities,
    }

    if partitions is None:
        # Rebuild from the flat entities list, using the standard mapping.
        from modules.evidence_vault.schemas.entity_schema import EntityRecord as _ER
        from modules.evidence_vault.services.entity_partition_service import (
            partition_entities,
        )
        records: List[EntityRecord] = []
        for d in all_entities:
            try:
                records.append(_ER.model_validate(d))
            except Exception:
                continue
        partitions = partition_entities(records)

    partitions_payload = {
        "case_id": str(case_id),
        "generated_at": datetime.utcnow().isoformat(timespec="seconds"),
        "partitions": [p.model_dump(mode="json") for p in partitions],
    }

    chunks_p = chunks_index_path(case_id)
    entities_p = entities_index_path(case_id)
    partitions_p = partitions_index_path(case_id)

    chunks_p.write_text(json.dumps(chunks_payload, indent=2), encoding="utf-8")
    entities_p.write_text(json.dumps(entities_payload, indent=2), encoding="utf-8")
    partitions_p.write_text(json.dumps(partitions_payload, indent=2), encoding="utf-8")

    bound = logger.bind(scope="evidence.persistence")
    bound.info("Wrote case aggregates: chunks={} entities={} partitions={}",
               len(all_chunks), len(all_entities), len(partitions or []))
    return {
        "chunks": chunks_p,
        "entities": entities_p,
        "partitions": partitions_p,
    }


def load_case_chunks(case_id: int | str) -> Optional[Dict]:
    p = chunks_index_path(case_id)
    if not p.exists():
        return None
    return json.loads(p.read_text(encoding="utf-8"))


def load_case_entities(case_id: int | str) -> Optional[Dict]:
    p = entities_index_path(case_id)
    if not p.exists():
        return None
    return json.loads(p.read_text(encoding="utf-8"))


def load_case_partitions(case_id: int | str) -> Optional[Dict]:
    p = partitions_index_path(case_id)
    if not p.exists():
        return None
    return json.loads(p.read_text(encoding="utf-8"))
