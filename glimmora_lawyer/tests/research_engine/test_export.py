"""Export: JSON round-trip + markdown layout + PDF availability."""
from __future__ import annotations

import json


def _build_synth_answer(indexed_corpus, monkeypatch):
    from modules.research_engine.schemas.retrieval_schema import ResearchQuery
    from modules.research_engine.services import (
        retrieval_service, reranking_service, synthesis_service,
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
    return case_id, q, answer, ranked


def test_json_export_round_trips(indexed_corpus, monkeypatch):
    from modules.research_engine.schemas.answer_schema import ResearchAnswer
    from modules.research_engine.services.export_service import (
        export_answer_json,
    )
    _, _, answer, _ = _build_synth_answer(indexed_corpus, monkeypatch)
    raw = export_answer_json(answer)
    parsed = ResearchAnswer.model_validate_json(raw)
    assert parsed.answer_id == answer.answer_id
    assert len(parsed.strongest_authorities) == len(answer.strongest_authorities)


def test_markdown_export_has_required_sections(indexed_corpus, monkeypatch):
    from modules.research_engine.services.export_service import (
        export_answer_markdown,
    )
    _, _, answer, _ = _build_synth_answer(indexed_corpus, monkeypatch)
    md = export_answer_markdown(answer).decode("utf-8")
    assert "# Research Answer" in md
    assert "## Top answer" in md
    assert "## Strongest authorities" in md or "## Distinguishable" in md
    assert "## Excerpts" in md
    # Risk flags appear because fallback synthesis always adds at least one.
    assert "## Risk flags" in md
    assert "## Recommended next steps" in md


def test_pdf_export_is_available_or_explicit(indexed_corpus, monkeypatch):
    """reportlab is in requirements.txt; if it's importable in the test
    env, the PDF must be a non-empty PDF stream. If reportlab is not
    installed, returning empty bytes is the documented signal."""
    from modules.research_engine.services.export_service import (
        export_answer_pdf,
    )
    _, _, answer, _ = _build_synth_answer(indexed_corpus, monkeypatch)
    pdf = export_answer_pdf(answer)
    try:
        import reportlab  # noqa: F401
    except ImportError:
        assert pdf == b"", "PDF should be empty when reportlab missing"
    else:
        assert pdf.startswith(b"%PDF"), (
            "When reportlab is installed, PDF bytes must start with %PDF"
        )
        assert len(pdf) > 800, len(pdf)
