"""Sessions + downstream payload: feedback updates flow through."""
from __future__ import annotations


def _make_session(indexed_corpus, monkeypatch, pinned=None, unresolved=None):
    from modules.research_engine.schemas.retrieval_schema import ResearchQuery
    from modules.research_engine.services import (
        retrieval_service, reranking_service, synthesis_service,
        session_service,
    )
    monkeypatch.setattr(
        synthesis_service, "get_gemini_client",
        lambda: (None, None), raising=True,
    )
    case_id, *_ = indexed_corpus
    q = ResearchQuery(query_text="specific performance",
                      query_type="legal_question")
    hits = retrieval_service.search(case_id, q)
    ranked = reranking_service.rerank(case_id, q, hits)
    answer = synthesis_service.synthesize(case_id, q, ranked)
    sess = session_service.build_session(
        case_id, q, answer, ranked,
        pinned_document_ids=pinned or [],
        unresolved_questions=unresolved or [],
    )
    session_service.save_session(case_id, sess)
    return case_id, sess


def test_session_feedback_round_trip(indexed_corpus, monkeypatch):
    from modules.research_engine.services.session_service import (
        update_session_feedback, load_session,
    )
    case_id, sess = _make_session(indexed_corpus, monkeypatch)
    updated = update_session_feedback(
        case_id, sess.session_id,
        pinned_document_ids=["doc-test-001"],
        user_feedback="thumbs_up",
        unresolved_questions=["Does the 2018 amendment alter the rule?"],
        user_notes="Strong authority, cite first.",
    )
    assert updated is not None
    assert updated.user_feedback == "thumbs_up"
    assert updated.pinned_document_ids == ["doc-test-001"]
    assert updated.unresolved_questions == [
        "Does the 2018 amendment alter the rule?"
    ]

    fresh = load_session(case_id, sess.session_id)
    assert fresh.user_feedback == "thumbs_up"


def test_invalid_feedback_value_rejected(indexed_corpus, monkeypatch):
    import pytest
    from modules.research_engine.services.session_service import (
        update_session_feedback,
    )
    case_id, sess = _make_session(indexed_corpus, monkeypatch)
    with pytest.raises(ValueError):
        update_session_feedback(case_id, sess.session_id,
                                user_feedback="not_a_value")


def test_downstream_payload_aggregates_unresolved_questions(indexed_corpus,
                                                            monkeypatch):
    from modules.research_engine.services.outputs_service import build_downstream

    case_id, sess = _make_session(
        indexed_corpus, monkeypatch,
        unresolved=["Outcome under the 2018 amendment is unclear."],
    )
    payload = build_downstream(case_id)
    assert payload.session_count >= 1
    assert payload.corpus_doc_count >= 1
    # Lawyer-written unresolved question must come first.
    assert payload.unresolved_legal_issues, payload.unresolved_legal_issues
    assert payload.unresolved_legal_issues[0].startswith(
        "Outcome under the 2018 amendment"
    )
    # Case-strength signals exist and are floats in [0, 1].
    for k, v in payload.case_strength_signals.items():
        assert 0.0 <= v <= 1.0, f"{k}={v}"
    # Top authorities populated when sessions have strong picks.
    assert payload.top_authorities, "Expected at least one top authority"
