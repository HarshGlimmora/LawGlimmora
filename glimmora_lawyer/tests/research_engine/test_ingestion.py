"""Ingestion: text path + provenance fields end up populated."""
from __future__ import annotations


def test_ingest_text_persists_document(temp_root):
    from modules.research_engine.services.upload_service import ingest_text
    from modules.research_engine.services.persistence_service import load_document

    doc, log = ingest_text(
        case_id="case-1",
        title="Test Precedent",
        body="HEADNOTE\nSpecific performance discussion.\n\nFACTS\nFoo bar.",
        source_reference="manual-input",
    )

    assert doc.status == "extracted"
    assert doc.page_count == 1
    assert doc.meta.source_type == "plain_text"
    assert doc.meta.source_reference == "manual-input"
    assert log.result == "completed"

    # Round-trip from disk.
    fresh = load_document("case-1", doc.document_id)
    assert fresh is not None
    assert fresh.full_text.startswith("HEADNOTE")


def test_metadata_confidence_score_set_after_enrich(sample_doc):
    """confidence_score must move out of 0.0 once enrich fills the fields."""
    case_id, doc = sample_doc
    # sample_doc fixture sets confidence_score=1.0 via the regex helper.
    assert 0.0 < doc.meta.confidence_score <= 1.0
    assert doc.meta.source_type == "pdf_upload"
    assert doc.meta.source_reference  # non-empty
