"""Reranking: all 8 factors populated + final_score interpretable."""
from __future__ import annotations


def test_rerank_populates_all_eight_factors(indexed_corpus):
    from modules.research_engine.schemas.retrieval_schema import ResearchQuery
    from modules.research_engine.services.retrieval_service import search
    from modules.research_engine.services.reranking_service import rerank

    case_id, *_ = indexed_corpus
    query = ResearchQuery(
        query_text="specific performance Section 10 Specific Relief Act",
        query_type="legal_question",
        jurisdiction_filter="India",
        issue_filter=["specific performance"],
        practice_area_filter=["contract"],
    )
    hits = search(case_id, query)
    ranked = rerank(case_id, query, hits)
    assert ranked, "Should rerank at least one hit"
    top = ranked[0]
    bd = top.breakdown
    # All eight factors must be in [0, 1].
    for name in ("jurisdiction_match", "court_rank", "issue_overlap",
                 "fact_similarity", "outcome_alignment", "recency",
                 "authority_level", "doctrinal_relevance"):
        v = getattr(bd, name)
        assert 0.0 <= v <= 1.0, f"{name}={v} out of [0,1]"
    # final_score must reflect a non-trivial multi-factor blend.
    assert top.final_score > 0.3, top.final_score
    # With matching jurisdiction + Supreme Court + matching issue,
    # the strongest signals should land at 1.0.
    assert bd.jurisdiction_match == 1.0
    assert bd.court_rank == 1.0
    assert bd.issue_overlap == 1.0
    assert bd.doctrinal_relevance >= 0.5


def test_rerank_deterministic_order(indexed_corpus):
    """Same input → same ranking. Cheap regression guard against
    non-deterministic dict ordering or unstable sort keys."""
    from modules.research_engine.schemas.retrieval_schema import ResearchQuery
    from modules.research_engine.services.retrieval_service import search
    from modules.research_engine.services.reranking_service import rerank

    case_id, *_ = indexed_corpus
    q = ResearchQuery(query_text="specific performance damages",
                      query_type="legal_question")
    hits = search(case_id, q)
    a = [r.chunk_id for r in rerank(case_id, q, hits)]
    b = [r.chunk_id for r in rerank(case_id, q, hits)]
    assert a == b
