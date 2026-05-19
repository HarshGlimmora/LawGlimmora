"""Shared pytest fixtures for Package 2 tests.

Every fixture is scoped per-test to keep state isolated. We point the
persistence root at a temp directory so the production `cases/` tree is
never touched, and we use deterministic document_ids so assertions are
stable across runs.
"""
from __future__ import annotations

import datetime as _dt
import pathlib
import sys

import pytest

# Make `import modules.research_engine...` resolve when pytest is invoked
# from anywhere in the repo.
_ROOT = pathlib.Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))


SAMPLE_JUDGMENT = """\
IN THE SUPREME COURT OF INDIA
CIVIL APPEAL NO. 4321 OF 2019

Acme Industries Pvt Ltd vs Zenith Holdings Pvt Ltd

Date of Judgment: 12-08-2019
Hon'ble Justice R. Banerjee
Hon'ble Justice S. Mehta

HEADNOTE
The Court held that specific performance under Section 10 of the Specific
Relief Act, 1963 is discretionary but must be granted where damages are
inadequate. Immovable property is presumed unique.

FACTS
The appellant entered into an agreement for sale on 15 March 2017. The
respondent refused to execute the sale deed. The appellant sued for
specific performance under Section 10 of the Specific Relief Act, 1963.

ISSUES
1. Whether specific performance can be granted when damages are an adequate remedy?
2. Whether the appellant was ready and willing to perform?

ARGUMENTS
Learned counsel for the appellant submitted that the property was unique
and damages would not suffice. The respondent's counsel argued readiness
was not established and that the agreement was unenforceable.

RATIO DECIDENDI
Specific performance under Section 10 is the rule and damages the
exception in cases of immovable property under the Specific Relief Act.

HELD
The appeal is allowed. The trial court decree of specific performance is
restored. Order accordingly.
"""


@pytest.fixture
def temp_root(tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch):
    """Redirect per-case persistence into an isolated temp directory.

    `config.settings.SETTINGS` is a frozen dataclass, so we cannot mutate
    its `root_dir` attribute. Instead we monkeypatch the `cases_root()`
    function in `persistence_service` — every other helper in the
    package routes through it, so a single patch is enough.
    """
    from modules.research_engine.services import persistence_service

    def _fake_cases_root():
        root = tmp_path / "cases"
        root.mkdir(parents=True, exist_ok=True)
        return root

    monkeypatch.setattr(persistence_service, "cases_root", _fake_cases_root,
                        raising=True)
    return tmp_path


@pytest.fixture
def sample_doc(temp_root):
    """A fully-built PrecedentDocument persisted to the temp case folder.

    Returns the doc so individual tests can chain further pipeline steps.
    """
    from modules.research_engine.schemas.corpus_schema import (
        PrecedentDocument, PrecedentMeta, PrecedentPage,
    )
    from modules.research_engine.services.metadata_service import _to_meta, _via_regex
    from modules.research_engine.utils.court_hierarchy import infer_binding_level
    from modules.research_engine.services import persistence_service

    case_id = "pkg2-test"
    doc = PrecedentDocument(
        document_id="doc-test-001",
        case_id=case_id,
        filename="acme_vs_zenith.pdf",
        ingested_at=_dt.datetime(2026, 5, 19, 10, 0, 0),
        page_count=1,
        full_text=SAMPLE_JUDGMENT,
        pages=[PrecedentPage(page_number=1, text=SAMPLE_JUDGMENT)],
        meta=PrecedentMeta(
            document_id="doc-test-001",
            source_type="pdf_upload",
            source_reference="acme_vs_zenith.pdf",
        ),
        status="extracted",
    )
    parsed = _via_regex(SAMPLE_JUDGMENT)
    parsed["document_id"] = doc.document_id
    parsed["practice_areas"] = ["contract", "specific relief"]
    parsed["issue_tags"] = ["specific performance", "immovable property",
                            "section 10"]
    parsed["outcome"] = "allowed"
    doc.meta = _to_meta(parsed)
    doc.meta.binding_level = infer_binding_level(doc.meta.court)
    doc.meta.source_type = "pdf_upload"
    doc.meta.source_reference = doc.filename
    doc.meta.confidence_score = 1.0
    persistence_service.save_document(case_id, doc)
    return case_id, doc


@pytest.fixture
def indexed_corpus(sample_doc):
    """Single-doc corpus with chunks built and indexes rebuilt."""
    from modules.research_engine.services import (
        chunking_service, indexing_service,
    )
    case_id, doc = sample_doc
    chunks = chunking_service.build_and_save_chunks(case_id, doc)
    summary = indexing_service.rebuild_index(case_id)
    return case_id, doc, chunks, summary
