"""Group a flat entity list into legal-meaning partitions."""
from __future__ import annotations

from typing import List

from loguru import logger

from modules.evidence_vault.schemas.entity_schema import (
    PARTITION_FOR_TYPE, PARTITION_TYPES, EntityRecord, Partition,
)


def partition_entities(entities: List[EntityRecord]) -> List[Partition]:
    """Returns one Partition per known group, in the canonical order.

    Entities with an unrecognised type are skipped (logged) — they should not
    appear because the EntityRecord schema is type-constrained, but we guard
    against schema drift from future Gemini outputs.
    """
    bound = logger.bind(scope="evidence.partition")
    buckets: dict[str, List[EntityRecord]] = {p: [] for p in PARTITION_TYPES}
    unknown = 0
    for ent in entities:
        ptype = PARTITION_FOR_TYPE.get(ent.entity_type)
        if not ptype:
            unknown += 1
            continue
        buckets[ptype].append(ent)
    if unknown:
        bound.warning("{} entity(ies) had no partition mapping — dropped from partitions.",
                      unknown)

    out: List[Partition] = []
    for ptype in PARTITION_TYPES:
        out.append(Partition(partition_type=ptype, entities=buckets[ptype]))  # type: ignore[arg-type]
    bound.info("Partitions built: {}",
               ", ".join(f"{p.partition_type}={len(p.entities)}" for p in out))
    return out
