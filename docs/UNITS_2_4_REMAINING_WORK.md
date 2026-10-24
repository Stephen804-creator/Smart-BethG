# Units 2–4: Remaining Work and Completion Gates

Status: in progress on the Units 1–4 feature branch.

## Unit 2 — Shared storage
Implemented foundation: owner-scoped local/S3-compatible adapters, uploads and
artifacts routed through adapters, path/owner checks, and a dry-run-first
migration utility for database-referenced local uploads/artifacts.

Not complete: repository-wide inventory of filesystem access; migration of any
other live durable workspace/research/social/mission/workflow paths; cross-instance
integration tests; backup/restore and rollback validation; orphan cleanup; and a
production migration rehearsal. Multi-instance readiness must not be claimed
until these gates pass.

## Unit 3 — Memory
Implemented foundation: typed/bounded memory context, provenance and expiry,
plus conservative conflict signals for similar statements with polarity or
numeric differences. Conflict signals are warnings only; both memories remain
available and the system does not decide which one is true.

Deferred: provider-backed semantic retrieval with budget controls, richer
contradiction analysis, and auditable preview/approval-based consolidation.

## Unit 4 — Knowledge and evidence
Implemented foundation: bounded chunking, keyword/optional embedding retrieval,
source labels, and conservative disagreement flags for similar excerpts with
polarity/numeric differences. A disagreement signal is not independent
verification and must not be presented as a truth judgment.

Deferred: image-only OCR, advanced reranking evaluated against labelled
benchmarks, independent external-source verification, and richer claim-to-
citation analysis.

## Verification gates before merging PR #12
- [ ] Run the full unit test suite against the current branch head.
- [ ] Run PostgreSQL integration/migration tests, including migration 0003.
- [ ] Verify S3 migration in a disposable test bucket: dry-run, apply, interrupted
  update, owner isolation, and rollback.
- [ ] Test conflict signals for genuine disagreements and unrelated claims.
- [ ] Inspect CI logs and resolve failures; a queued workflow or passing security
  check alone does not establish that the tests passed.
- [ ] Update this document and the foundation audit with observed results.
