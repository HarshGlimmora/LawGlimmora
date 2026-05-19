"""Chunking: section cues + paragraph anchors + disposition detection."""
from __future__ import annotations


def test_chunks_produced_with_section_types(sample_doc):
    from modules.research_engine.services.chunking_service import build_chunks
    case_id, doc = sample_doc
    chunks = build_chunks(doc)
    assert len(chunks) >= 3, "Sample judgment should produce multiple chunks"
    types = {c.chunk_type for c in chunks}
    # We expect at least these structural sections to fire on the sample.
    assert types & {"headnote", "facts", "issues", "ratio", "holding",
                    "disposition", "arguments"}, (
        f"Expected at least one structural chunk_type, got {types}"
    )


def test_disposition_section_detected(sample_doc):
    """The sample judgment contains 'Order accordingly' — should map to
    `disposition`, not `holding`."""
    from modules.research_engine.services.chunking_service import build_chunks
    _, doc = sample_doc
    chunks = build_chunks(doc)
    dispo = [c for c in chunks if c.chunk_type == "disposition"]
    assert dispo, (
        "Expected a disposition chunk from 'The appeal is allowed' / "
        "'Order accordingly' in the sample text"
    )


def test_citation_labels_well_formed(sample_doc):
    from modules.research_engine.services.chunking_service import build_chunks
    _, doc = sample_doc
    chunks = build_chunks(doc)
    for c in chunks:
        lab = c.citation_anchor.citation_label
        assert lab.startswith("["), lab
        assert "p. " in lab, lab
        assert "chunk " in lab, lab
        assert doc.filename in lab, lab
