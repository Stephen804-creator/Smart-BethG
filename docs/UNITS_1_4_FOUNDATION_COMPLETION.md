# Units 1–4 foundation completion

This branch is based on `main` and intentionally excludes the separate UI/UX work in PR #14 and the Units 5–9 implementation in PR #13.

## Unit 1 — Foundation audit
The existing `architecture.md`, `roadmap.md`, and README document deployment constraints and open launch gates. Treat those gaps as open until their verification evidence exists; documentation alone is not a production-readiness claim.

## Unit 2 — Shared storage
The owner-scoped local and S3-compatible storage adapters and `scripts/migrate_local_storage.py` already exist. The migration utility defaults to dry-run, verifies copied bytes, uses a compare-and-set database update, and keeps source files. Remaining multi-instance filesystem inventory, shared-storage integration tests, backup/restore, orphan cleanup, rollback, and a production migration rehearsal remain open. Do not enable multiple instances merely because the adapter exists.

## Unit 3 — Advanced memory
Typed memories, provenance fields, expiry, bounded context assembly, and conservative conflict signals already exist. Semantic retrieval with model-version tracking, expanded conflict review, and approval-based versioned consolidation remain open.

## Unit 4 — Knowledge and evidence
This branch adds optional OCR for image uploads and image-only/scanned PDFs. OCR is bounded by upload limits, a pixel limit, page limit, and timeout. OCR is optional: standard text extraction does not require it, and missing OCR dependencies return a clear message rather than silently treating a scan as empty text.

Install Python extras with `pip install -r requirements-ocr.txt` and install the Tesseract executable plus Poppler (needed by pdf2image) using the operating system's package manager. These system dependencies are not installed by pip. Environment controls:
- `SMART_BETHG_OCR_MAX_IMAGE_PIXELS` (default 16,000,000)
- `SMART_BETHG_OCR_TIMEOUT_SECONDS` (default 12)
- `SMART_BETHG_OCR_MAX_PAGES` (default 5, hard-capped at 10)

Still open: labelled retrieval-quality evaluation before selecting a reranker; external-source verification through approved connectors with provenance; stronger source-disagreement analysis and claim-to-citation coverage. Do not represent heuristic disagreement signals as proof.

## Verification status
This change has not yet been validated by the repository's PostgreSQL-backed test suite or a real OCR runtime. Run `python -m unittest discover -s tests -p "test_*.py" -v` against a disposable PostgreSQL test database, then exercise text PDFs, scanned PDFs, image uploads, oversized images, and OCR timeout behavior before marking the PR ready.
