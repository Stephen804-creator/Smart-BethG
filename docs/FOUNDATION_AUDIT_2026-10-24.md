# Smart BethG Foundation Audit — 2026-10-24

**Repository:** `Stephen804-creator/Smart-BethG`  
**Baseline:** `main`, commit `eb1eefb1a2528ebf95fe856fd65d8c8279577755`  
**Purpose:** establish a repository-grounded baseline for roadmap Units 1–4. This is a code/documentation review, not a live-host audit, penetration test, or launch approval.

## Executive summary

The repository already has a substantial FastAPI/PostgreSQL application. It has user-scoped file, memory, and knowledge repositories; file extraction for supported text files and PDFs; chunked knowledge ingestion; optional embeddings with usage-budget reservations; keyword fallback; model-specific vector filtering; project and conversation memory scopes; evidence and research records; and automated tests. These capabilities should be extended, not replaced.

The repository's own dated whole-codebase audit remains relevant for production limitations. Its CI results are historical to the revisions named in that audit and must not be treated as verification of this branch's current head.

## Unit 1 — What exists and what remains

| Area | Baseline finding | Action in this change |
|---|---|---|
| Database | PostgreSQL-only runtime and numbered migrations already exist | Add a new migration; do not rewrite the baseline migration |
| File storage | Upload and artifact services store local filesystem paths | Introduce a storage adapter for local and S3-compatible object storage |
| Ownership | File/artifact repositories scope lookups and deletes by user | Keep owner-scoped DB lookup before storage operations; add adapter-level owner-prefix checks |
| Memory | Persistent user/project/conversation scopes and user deletion exist | Add typed memory, confidence, provenance, metadata, expiry, and bounded type-aware retrieval |
| Knowledge | Fixed-size chunks, optional embeddings, and keyword fallback exist | Add boundary-aware chunking, atomic index replacement, ranked lexical search, and source citations |
| Evidence | Research/evidence records exist; review status is not proof of independent verification | Keep source status honest; expose uploaded-file provenance and label excerpts as unverified evidence |
| Tests | Unit and PostgreSQL test suites exist | Add regression tests for storage isolation, advanced memory, and retrieval ranking |

## Unit 2 — Storage readiness

The new adapter contract supports owner-scoped byte writes, reads, and deletion. The local adapter is intended for development and single-instance operation. The S3-compatible adapter supports AWS S3 or compatible object stores and stores locators as `s3://bucket/key`. Configure `SMART_BETHG_OBJECT_STORAGE=s3`, `SMART_BETHG_S3_BUCKET`, and optionally `SMART_BETHG_S3_PREFIX`, `SMART_BETHG_S3_REGION`, and `SMART_BETHG_S3_ENDPOINT_URL`; credentials should come from the hosting environment/standard AWS credential chain, never from source code.

The file and artifact services use the adapter. Workspaces and every other filesystem-backed subsystem still require an inventory and adapter migration before multi-instance deployment can be declared ready. Local mode is not shared storage. Do not scale replicas merely because the S3 adapter exists; test cross-instance read/write/delete and provider permissions first.

## Unit 3 — Memory readiness

The existing three scopes remain in place to avoid needless duplication. New metadata distinguishes episodic, semantic, procedural, preference, policy, and evidence memory; records confidence and source references; supports structured metadata and optional expiry; and bounds injected context by count and characters. Expired or malformed-expiry records are excluded from model context but remain visible in the user's review list so they can be managed.

These fields do not automatically infer truth, resolve contradictions, or prove a memory is correct. Future conflict resolution and semantic retrieval must retain provenance and user controls.

## Unit 4 — Knowledge and evidence readiness

Existing optional embedding retrieval and keyword fallback are retained. Chunking now prefers paragraph/sentence boundaries within the size bound; re-indexing replaces chunks in one transaction; lexical retrieval uses document-frequency weighting; and returned excerpts include a source filename/file/chunk citation label and retrieval method. Uploaded-file excerpts are explicitly labeled as evidence rather than independently verified facts.

This is not a complete external-source fact-checker. URL/source verification, reranking with a cross-encoder, OCR for image-only PDFs, and contradiction analysis remain future work. The system must never invent URLs or cite a source it did not retrieve.

## Verification and remaining gates

The repository connector can write the proposed changes, but only GitHub Actions on the resulting commit can establish whether the code compiles and the regression suites pass. Do not claim the changes are verified until the current branch-head unit, PostgreSQL integration, dependency, and secret-scan workflows finish successfully.

Still outstanding for launch: shared workspace storage, complete multi-instance tests, broader PostgreSQL coverage and migration rehearsal, password recovery/session revocation hardening, a deliberate CSP policy, full data export/deletion, backup/restore drills, independent security review, load/failure testing, live-host verification, and qualified legal/privacy review.
