# Evidence Vault — Package 1 (Phase 1 + Phase 2)

Scope shipped:

**Phase 1**
1. PDF upload + case attach
2. Page-by-page text extraction (PyMuPDF / `fitz`)
3. Light legal-text cleaning
4. Canonical JSON generation (forward-compatible top-level shape)
5. Per-page citation anchors
6. Local per-case persistence
7. Per-document structured extraction log

**Phase 2 (this layer)**
8. Hybrid legal chunking (structural segmentation + size normalisation)
9. Chunk-level citation anchors `[file | p.X-Y | chunk N]`
10. Entity extraction — Vertex AI Gemini primary, AI Studio fallback, deterministic regex final fallback
11. Entity normalisation (ISO dates, numeric amounts, canonical sections/clauses/acts)
12. Entity partitioning into the 5 legal meaning groups (`parties`, `timeline`, `legal_basis`, `factual_evidence`, `procedural_facts`)
13. Per-case aggregates: `chunks.json`, `entities.json`, `partitions.json`
14. Streamlit: Canonical Store tab shows chunk cards with filters; Entity RAG Explorer tab supports partition / type / page / chunk / confidence / search filters

Not yet: contradictions · missing evidence · chat · retrieval / scoring.

## Folder layout

```
modules/evidence_vault/
  pages/
    evidence_vault_page.py          # Streamlit entry — owns the three tabs
  services/
    upload_service.py               # Validate + save raw PDF + log
    extraction_service.py           # PyMuPDF page-by-page extraction
    cleaning_service.py             # Legal-aware text normalisation
    persistence_service.py          # Folders, canonical JSON, per-doc logs
    citation_service.py             # Page-level citation anchors
  schemas/
    evidence_schema.py              # Pydantic canonical structure
  utils/
    file_utils.py                   # hash, sanitise, path helpers
    text_utils.py                   # word/char counts, sentence splitter
  logs/
    extraction.log                  # global extraction log (loguru sink)
```

## Persistence layout (per case)

```
cases/<case_id>/evidence/
  raw/<document_id>__<sanitised_filename>.pdf
  extracted/<document_id>.json       # canonical JSON
  chunks/                            # reserved for next phase
  entities/                          # reserved for next phase
  reports/                           # reserved for next phase
  logs/<document_id>_log.json        # per-doc extraction log
```

The persistence root is `<project_root>/cases/<case_id>/evidence/` — case-scoped, no user prefix.

## Canonical JSON (top-level)

The full schema is in [evidence_schema.py](schemas/evidence_schema.py). Top-level shape:

```jsonc
{
  "document": { "document_id": "...", "case_id": "...", "filename": "...",
                "evidence_title": "...", "doc_type": "FIR", "source": "user_upload",
                "language": "en", "jurisdiction": "India",
                "uploaded_at": "2026-05-19T10:34:00", "page_count": 12,
                "processing_status": "completed" },
  "pages":   [ /* per-page records with raw + clean text, hash, counts,
                  per-page citation, plus empty entities/claims slots */ ],
  "chunks":              [],
  "entities":            [],
  "claims":              [],
  "contradictions":      [],
  "missing_evidence":    [],
  "argument_recommendations": [],
  "summary": { "total_pages": 12, "total_characters": 14530,
               "total_words": 2410, "extraction_duration_ms": 421 }
}
```

The empty arrays/objects are intentional — downstream packages (chunking, entities, contradictions, missing, argument recs) populate them in-place without changing the schema.

## Page object

Every page record carries:

| Field | Meaning |
|---|---|
| `page_number` | 1-indexed page number |
| `raw_text` | Unmodified `page.get_text("text")` output |
| `clean_text` | After `cleaning_service` normalisation |
| `page_hash` | SHA-256 (first 16 chars) of `clean_text` — for dedupe & integrity |
| `character_count`, `word_count` | Computed on `clean_text` |
| `citations` | Array containing the page-level citation anchor (today: one) |
| `entities`, `claims` | Empty arrays — reserved for next phase |

## Citation anchor

```jsonc
{
  "citation_id": "<uuid>",
  "document_id": "<doc_id>",
  "filename": "fir_pune.pdf",
  "page_number": 1,
  "citation_label": "[fir_pune.pdf | p.1]"
}
```

Page-level for now. When chunking lands, additional citation rows at the chunk level will be appended.

## Processing flow (locked order)

1. PDF received via Streamlit uploader
2. Validate (PDF type + non-empty + duplicate-filename warning)
3. Generate `document_id`
4. Save raw PDF to `cases/<case_id>/evidence/raw/`
5. Extract pages via PyMuPDF
6. Clean each page's text
7. Build `PageRecord`s with hash + counts + page citation
8. Build the full canonical JSON
9. Persist JSON to `cases/<case_id>/evidence/extracted/`
10. Persist per-doc structured log to `cases/<case_id>/evidence/logs/`
11. Display extraction result + status cards in the Streamlit UI

## Run

```bash
cd glimmora_lawyer
source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

Demo logins one-click on the landing page. Open any case → "Open Evidence Vault" → use the three tabs.
