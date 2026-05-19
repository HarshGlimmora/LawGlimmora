"""Synthesis fallback: when no LLM is available, produce a grounded
answer with strongest/distinguishable tiers split correctly."""
from __future__ import annotations


def test_fallback_synthesis_grounds_to_retrieved_chunks(indexed_corpus,
                                                       monkeypatch):
    from modules.research_engine.schemas.retrieval_schema import ResearchQuery
    from modules.research_engine.services import (
        retrieval_service, reranking_service, synthesis_service,
    )

    # Force the Gemini path off by stubbing `get_gemini_client`.
    monkeypatch.setattr(
        synthesis_service, "get_gemini_client",
        lambda: (None, None), raising=True,
    )

    case_id, *_ = indexed_corpus
    query = ResearchQuery(
        query_text="specific performance immovable property",
        query_type="legal_question",
    )
    hits = retrieval_service.search(case_id, query)
    ranked = reranking_service.rerank(case_id, query, hits)
    answer = synthesis_service.synthesize(case_id, query, ranked)

    assert answer.synthesis_source == "fallback"
    assert answer.top_answer
    assert answer.strongest_authorities, "Fallback must surface authorities"
    # Every authority must be reachable in the ranked set.
    ranked_doc_ids = {r.document_id for r in ranked}
    for a in answer.strongest_authorities + answer.distinguishable_authorities:
        assert a.document_id in ranked_doc_ids, (
            f"Authority {a.document_id} not in retrieved set"
        )
    # No invented citations: every excerpt label must appear in the ranked set.
    ranked_labels = {r.citation_label for r in ranked}
    for e in answer.excerpts:
        assert e.citation_label in ranked_labels, (
            f"Excerpt label {e.citation_label} not grounded"
        )
    # Tier discipline: strongest and distinguishable lists must be disjoint.
    strong_ids = {a.document_id for a in answer.strongest_authorities}
    dist_ids = {a.document_id for a in answer.distinguishable_authorities}
    assert strong_ids.isdisjoint(dist_ids), (
        "Tiers must be disjoint by document_id"
    )


def test_fallback_handles_empty_retrieval(temp_root, monkeypatch):
    from modules.research_engine.schemas.retrieval_schema import ResearchQuery
    from modules.research_engine.services import synthesis_service
    monkeypatch.setattr(
        synthesis_service, "get_gemini_client",
        lambda: (None, None), raising=True,
    )
    q = ResearchQuery(query_text="anything", query_type="legal_question")
    answer = synthesis_service.synthesize("empty-case", q, [])
    assert answer.synthesis_source == "fallback"
    assert answer.strongest_authorities == []
    assert "empty_retrieval" in answer.risk_flags
    assert answer.next_steps, "Even on empty retrieval, suggest next steps"
