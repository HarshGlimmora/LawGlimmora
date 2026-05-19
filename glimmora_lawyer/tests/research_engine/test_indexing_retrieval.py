"""Indexing + retrieval: BM25 hit count + filter behaviour."""
from __future__ import annotations


def test_index_written_to_disk(indexed_corpus):
    from modules.research_engine.services.persistence_service import (
        bm25_path, metadata_index_path,
    )
    case_id, doc, _, summary = indexed_corpus
    assert bm25_path(case_id).exists()
    assert metadata_index_path(case_id).exists()
    assert summary["docs"] == 1
    assert summary["chunks"] >= 3


def test_retrieval_returns_hits_for_substantive_query(indexed_corpus):
    from modules.research_engine.schemas.retrieval_schema import ResearchQuery
    from modules.research_engine.services.retrieval_service import search

    case_id, *_ = indexed_corpus
    query = ResearchQuery(
        query_text="specific performance immovable property damages",
        query_type="legal_question",
    )
    hits = search(case_id, query)
    assert len(hits) >= 1, f"Expected at least one hit, got {hits}"
    assert all(h.raw_score > 0 for h in hits)


def test_jurisdiction_filter_excludes_non_matching(indexed_corpus):
    """All sample docs have jurisdiction=India. Filter to a fake one and
    expect zero hits (the structured filter should kick in before BM25)."""
    from modules.research_engine.schemas.retrieval_schema import ResearchQuery
    from modules.research_engine.services.retrieval_service import search

    case_id, *_ = indexed_corpus
    query = ResearchQuery(
        query_text="specific performance",
        query_type="legal_question",
        jurisdiction_filter="Atlantis",
    )
    hits = search(case_id, query)
    assert hits == [], f"Filter should exclude all docs, got {hits}"


def test_citation_lookup_helper(indexed_corpus):
    """The /lookup/citation endpoint logic boils down to a substring match
    over the metadata index — verify the underlying data is queryable."""
    from modules.research_engine.services.indexing_service import (
        load_metadata_index,
    )
    case_id, _, _, _ = indexed_corpus
    md = load_metadata_index(case_id)
    assert md, "metadata index should be populated"
    # Title contains 'Acme'
    matches = [d for d in md if "acme" in (d.get("title") or "").lower()]
    assert matches, f"Expected to find Acme via title, got {md}"
