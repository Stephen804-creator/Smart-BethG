# Asset Provenance and Attribution — Product, Technical Design, and Execution Plan

**Status:** Approved implementation plan; Unit 0 baseline inspection completed. Implementation follows this document in order.  
**Created:** 2026-11-03  
**Target repository:** `Stephen804-creator/Smart-BethG`  
**Working branch:** `feat/asset-provenance-attribution-2026-11-03`  
**Base:** `main`  
**Feature name:** Asset Provenance and Attribution (APA)

## 1. Purpose

Build a first-party Smart BethG capability that records the origin and lifecycle of digital assets produced, transformed, or coordinated through Smart BethG. The feature must make it possible to answer:

- Who or what initiated an asset?
- Which human instructions, source assets, AI providers/models, agents, and Smart BethG workflows contributed?
- Which transformations, edits, reviews, and approvals occurred, and in what order?
- What exact bytes were produced at each recorded asset version?
- Has the asset or its provenance record changed since it was signed?
- Can provenance be exported in a standards-oriented form without falsely claiming official C2PA conformance or trusted organisational identity?

This is an individual-developer feature. Company registration, C2PA membership, paid certification, and an officially trusted organisational signing identity are **not prerequisites** for development or initial use.

## 2. Product outcome and boundaries

### 2.1 Initial user outcome

An authenticated user can upload or create a supported asset, attach provenance information, record AI/human contributions and transformations, review its timeline, generate a cryptographically signed provenance statement when signing is configured, verify the asset and statement later, and export a portable provenance package.

The first implementation must work with the existing Smart BethG artifact library and must not require a separate application or service.

### 2.2 Supported initial asset types

- Text and document-like UTF-8 files.
- Images (initially common JPEG, PNG, and WebP formats).
- Video files (initially MP4 and WebM containers).

The upload pipeline must validate declared media type against file signatures where practical, enforce configurable size limits, stream or bounded-read data, and use the existing storage adapter. Unsupported or ambiguous formats must be rejected or stored without a misleading verified media-type claim.

### 2.3 Explicit non-goals

- No company registration or legal-entity identity workflow.
- No paid C2PA certification or C2PA organisation membership.
- No claim that self-generated development keys are trusted by public verification services.
- No automatic assertion that Smart BethG generated an asset merely because it orchestrated a provider.
- No automatic capture of private prompts, uploaded source bytes, secrets, or unrelated conversation history into public manifests.
- No claim that provenance proves an asset is truthful, authentic in the real-world sense, copyright-owned, or free from manipulation.
- No replacement of existing artifact storage, workflow, decision-ledger, or provider-routing systems.
- No broad redesign of the artifact library UI.

## 3. Core attribution rules

These rules are mandatory and apply to every implementation unit.

1. **Separate contributors.** Record the human, Smart BethG agent/orchestrator, external provider, and model as distinct contributor roles. A provider/model is not the same thing as Smart BethG.
2. **Record actual execution.** Use the provider and model that actually returned the successful result, including fallback provider/model when fallback occurred. Do not record only the initially requested model.
3. **No fabricated lineage.** If a provider, model, agent, source asset, or transformation is unknown, record it as unknown/not supplied. Never infer it from a user-facing label.
4. **Hash exact bytes.** SHA-256 is calculated over the exact stored asset bytes. A hash identifies bytes; it does not establish authorship or truth.
5. **Append lifecycle events.** Creation, contribution, transformation, review, approval, signing, verification, and export events are recorded as ordered events. Normal API paths do not rewrite historical events.
6. **Owner isolation.** Every asset, event, manifest, and verification lookup is scoped to the authenticated owner. No ID-only lookup may disclose another user's record.
7. **Privacy by design.** Store prompt/instruction text only when the user explicitly chooses to include it. Otherwise store a digest and a user-editable summary. Never store provider credentials, authentication tokens, session cookies, or secret environment values in provenance.
8. **Honest signing state.** Distinguish unsigned, signed-with-development-key, signed-with-configured-key, invalid, and unverifiable states. Missing or ephemeral signing configuration must never produce a successful signature claim.
9. **Honest standards status.** A portable internal JSON statement is not a C2PA manifest. A C2PA export is labelled C2PA only after it is generated and validated by a compatible implementation. Neither local success nor a self-signed certificate implies official trust or certification.
10. **Deletion and retention.** Provenance data is user data. Asset deletion and account deletion must follow existing privacy/retention policy and must not leave hidden personal data indefinitely. A cryptographic signature is not a reason to deny an authorised deletion request.

## 4. Current repository integration points

The implementation must inspect and extend the actual base-branch code, not assume paths or interfaces from older branches.

Baseline inspected at main commit `b8b632d9a856ea16528fde39c5355965cfa38e21` (2026-11-01). The feature branch was created from that exact `main` head. The plan itself was committed first as `a4edb28f1e561d7cffd68213429b246789a332ec`. The current migration sequence ends at `0011_workflow_adapter_idempotency.sql`; Unit 1 will add `0012_asset_provenance.sql`. Existing artifact persistence is text-only (1 MiB) and uses `put_bytes`; binary support is therefore a real additive extension, not an existing capability. `cryptography>=50` is already a production dependency, so Ed25519 does not require a new dependency unless runtime compatibility review identifies a reason.

Known current-main integration points:

- `services/artifact_service.py`: owner-scoped artifact persistence and storage adapter use.
- `routes/artifacts.py`: authenticated artifact API.
- `storage/backend.py` and storage adapters: durable object storage.
- `database.py`: PostgreSQL-only application database and ordered migrations.
- `migrations/postgresql/`: additive, numbered schema migrations. Never edit a released migration.
- `services/chat_service.py`: actual provider/model execution and fallback handling.
- `providers/provider_manager.py`: provider/model resolution.
- `services/units_11_15.py`: decision ledger and routing evidence, where present on the selected base.
- `api/dependencies.py`: authenticated user and service dependencies.
- `routes/pages.py`, `templates/`, and `static/js/`: page and frontend integration. **Baseline finding:** main has no artifact-library/detail UI yet; Unit 8 must create a focused Asset Library/Provenance page and link it from the existing navigation rather than pretending an artifact detail screen already exists.
- `config.MAX_UPLOAD_SIZE_BYTES`: current default upload ceiling is 15 MiB. Initial provenance uploads must respect the configured ceiling; do not silently raise the platform-wide upload limit for video.
- `tests/base.py`: PostgreSQL-backed test isolation.
- `tests/test_artifact_service.py`, route tests, provider/chat tests: regression patterns.

Before implementation, confirm the current branch's exact paths and interfaces. If a named integration point differs, update this plan with the observed path/interface before coding; do not create a duplicate subsystem.

## 5. Data model

The exact SQL names may be adjusted only to avoid collisions discovered during repository inspection. The following logical records are required.

### 5.1 Provenance event stream

One row per lifecycle event, with at least:

- Stable event ID.
- Owner/user ID.
- Related artifact ID.
- Event sequence number scoped to the artifact.
- Event type.
- Actor type: human, Smart BethG, external provider/model, or external tool.
- Actor identifier and display label, when known.
- Provider and model identifiers, when applicable.
- Agent/workflow/mission/conversation references, when available and authorised.
- Input asset references and SHA-256 hashes.
- Output asset reference and SHA-256 hash, when applicable.
- Transformation name/version and bounded structured parameters.
- Human contribution/approval details, when applicable.
- User-approved instruction summary and optional explicitly included instruction text.
- Timestamp generated by the server.
- Canonical event payload version and canonical payload digest.
- Previous-event digest and current-event digest to form a per-asset hash chain.

Event payloads must be schema-validated, bounded in size/depth, and must not accept arbitrary secrets or filesystem paths.

### 5.2 Provenance manifest

A versioned, portable JSON representation containing:

- Manifest schema identifier and version.
- Asset identity (opaque ID, media type, byte size, SHA-256).
- Creation timestamp and origin classification.
- Contributor list with explicit roles.
- Source asset references/hashes.
- Ordered transformation and approval history.
- Provenance event-chain head digest.
- Signing metadata and verification status.
- Standards/export metadata where relevant.

The manifest must not contain private storage locators, internal absolute paths, database connection details, or credentials.

### 5.3 Signature record

A signature record must identify:

- Algorithm and key ID.
- Signature bytes (encoded).
- Public key or a resolvable public-key identifier.
- Signed manifest digest.
- Signing timestamp.
- Key purpose/environment and trust classification.
- Verification result and reason when verification is performed.

Use an asymmetric signature (Ed25519) for portable public verification. Private keys must be supplied through deployment secrets or a secure key-management integration, never committed. A generated local development key is explicitly untrusted and must be labelled as such. If no stable configured signing key is available, provenance remains unsigned.

### 5.4 Database constraints

- Foreign keys and owner scoping must prevent cross-user references.
- Unique per-asset event sequence numbers.
- Indexes for owner/asset/timestamp and event lookups.
- Event and signature payloads must be bounded.
- New tables must be added in a new numbered PostgreSQL migration.
- Add database-level protections against ordinary updates to historical event payloads where feasible, while preserving authorised retention/deletion operations.
- Use transactions for event sequence allocation, event insertion, hash-chain update, and related artifact state changes.

## 6. API contract

Use the existing authenticated API conventions and version prefix.

Required endpoints (final route prefix follows the current API router layout):

- Create an asset with optional initial provenance metadata.
- Upload a binary asset with bounded streaming and content validation.
- Retrieve an asset's provenance summary.
- Retrieve the ordered provenance timeline.
- Append a contribution, transformation, review, or approval event.
- Generate or refresh the portable provenance manifest.
- Sign a manifest when a stable signing key is configured.
- Verify the asset bytes, event chain, manifest digest, and signature.
- Export a provenance package (asset plus manifest where permitted, or manifest-only).
- Delete an asset and apply the documented provenance retention/deletion behavior.

All endpoints must require authentication, enforce owner scope, use request validation, and return safe errors. Mutations must respect the application's CSRF protections and existing idempotency patterns where duplicate requests could create duplicate events or assets.

Do not expose private storage locators or signing private keys.

## 7. AI and agent attribution integration

### 7.1 Chat generation

Instrument the successful provider execution boundary in `ChatService`:

- Capture the actual provider and model returned by the successful call, not just the requested selection.
- Capture whether fallback was used.
- Associate the result with the originating user/conversation and, where a generated artifact is explicitly created from that result, link the artifact to the generation event.
- Do not automatically create a user-facing artifact for every chat response.
- Do not copy full conversation history into provenance.
- If instruction text is not explicitly included, retain only a digest and/or user-approved summary.

### 7.2 Other AI tools and workflows

Where an image/video/document generation adapter already exists on the selected branch, instrument its real success boundary. If no such adapter exists in the base branch, provide a documented service/API for explicit contribution events and leave automatic adapter integration for the later adapter-specific task. Never create a fake model execution record to fill a gap.

### 7.3 Human contribution

Support explicit records for user upload, edit, replacement, review, approval, rejection, and supplied source material. Human approval must identify the authenticated user and timestamp; it must not be inferred from a download or page view.

## 8. Security, privacy, and reliability requirements

- Authenticated owner-only access for all provenance records.
- No IDOR across asset IDs, event IDs, manifests, or verification endpoints.
- Validate upload size before and during reading; do not buffer unbounded request bodies.
- Verify media signatures and use safe download headers.
- Never execute uploaded assets or parse untrusted media using shell commands.
- Bound event JSON size, nesting, list counts, and string lengths.
- Protect signing keys; never log them or return them.
- Use canonical JSON serialization for deterministic digests.
- Use constant-time signature/digest comparisons where applicable.
- A changed asset must fail hash verification.
- A changed event or reordered event chain must fail chain verification.
- A missing key must return unverifiable/unsigned, not valid.
- Avoid duplicate events on retries through idempotency keys.
- Preserve existing artifact endpoints and response contracts unless an additive change is required.
- Ensure account export includes permitted provenance data and clearly identifies omitted binary content.
- Ensure asset/account deletion and retention behavior is consistent with the application's privacy commitments.
- No deployment, public release, or production-key provisioning is part of this task.

## 9. Standards and C2PA strategy

Implement in two distinct layers:

**Layer A — Smart BethG portable provenance (initial deliverable):** versioned JSON manifest, event-chain integrity, Ed25519 signatures, public-key verification, and downloadable provenance package. This is Smart BethG's own provenance format. It must not be called a C2PA credential or C2PA-certified output.

**Layer B — C2PA-compatible export (separate implementation unit):** evaluate and integrate a maintained C2PA implementation capable of creating and validating manifests for the supported media types. Map the internal contributor/action/source information to the applicable C2PA assertions. Keep unsupported internal fields in a clearly separate sidecar if the standard cannot represent them. Validate the produced manifest with an independent C2PA validator/tool where feasible.

C2PA signing requires a certificate chain and trust policy suitable for the intended ecosystem. A self-signed development certificate can be used only for local experiments and will not automatically be trusted by independent verifiers. Official conformance/certification and organisational identity are future operational/legal work, not part of this feature branch.

If a maintained library cannot be installed or safely validated for this repository/runtime, complete Layer A, document the exact blocker, and do not ship a fabricated C2PA-labelled file.

## 10. Ordered implementation units

Execute these units in order. Do not skip ahead or silently combine units. Update the completion checklist in this document after each unit with changed files, tests, commit SHA, and any deviation.

### Unit 0 — Repository baseline and change contract
1. Inspect branch status, README, architecture/decision documents, migration sequence, artifact routes/service, storage adapters, chat/provider flow, export/deletion behavior, and CI commands. **Completed:** inspected README, `database.py`, migrations, artifact service/routes, storage adapters, chat/provider services, API dependencies, app registration, requirements, and PostgreSQL test base.
2. Record the exact current baseline commit and any pre-existing work. **Completed:** base is `b8b632d9a856ea16528fde39c5355965cfa38e21`; work is isolated on `feat/asset-provenance-attribution-2026-11-03`; no changes were made to `main` or other open PR branches.
3. Confirm the final module names and route prefix. **Completed:** use `services/provenance_service.py`, `repositories/provenance_repository.py`, and `routes/provenance.py`; mount under `/api/v1/provenance` and retain artifact routes under `/api/v1/artifacts`.
4. Add or update this plan before implementation if repository evidence changes any decision. **Completed:** current main has a text-only artifact service, storage adapters expose `put_bytes/get_bytes/delete`, the migration sequence ends at `0011`, and `cryptography>=50` is already installed. Unit 2 must extend storage safely for bounded binary uploads.
5. Run the existing focused artifact/provider tests or record why the environment cannot run them. **Not run locally:** the available GitHub repository interface can inspect and change repository files but does not provide the disposable PostgreSQL test database required by `tests/base.py`. The documented focused and full suites remain mandatory CI verification after implementation.

**Acceptance:** completed by repository inspection; no application source code changed. Plan-only commit: `a4edb28f1e561d7cffd68213429b246789a332ec`.

### Unit 1 — PostgreSQL schema and domain contracts
1. Add a new numbered migration for provenance events, manifests, signatures, indexes, constraints, and sequence/hash-chain fields.
2. Add validated domain constants/schemas and canonical JSON/digest helpers.
3. Add transaction-safe repository methods for creating, listing, and retrieving owner-scoped provenance records.
4. Add tests for migration, canonicalization, event ordering, owner isolation, bounds, and append-only behavior.

**Acceptance:** clean migration applies; event rows are owner-scoped and ordered; tampered or out-of-order records are detectable.

### Unit 2 — Asset binary support and immutable byte identity
1. Extend the artifact service using the existing storage adapter; preserve current text behavior.
2. Add bounded binary upload and read paths for supported media types.
3. Validate size, media type, file signature, checksum, and storage result.
4. Record the initial asset-created/uploaded event and exact SHA-256.
5. Add tests for supported formats, mismatched MIME/signatures, oversized bodies, storage failures, checksum consistency, and owner isolation.

**Acceptance:** supported files can be stored/retrieved safely and the stored bytes have a reproducible SHA-256 identity.

### Unit 3 — Provenance event service and timeline API
1. Implement typed lifecycle events for source, contribution, transformation, edit, review, approval/rejection, and export.
2. Allocate sequence numbers and append hash-chained events transactionally.
3. Enforce idempotency for retryable mutations.
4. Add authenticated owner-scoped API endpoints and response schemas.
5. Add tests for lifecycle ordering, duplicate retries, invalid transitions, cross-owner access, and concurrent event appends.

**Acceptance:** a user can create and retrieve a complete ordered timeline without editing prior event payloads.

### Unit 4 — Real AI/provider/agent attribution
1. Trace the actual successful ChatService provider/model and fallback result.
2. Record provider/model/Smart BethG orchestrator as separate contributors.
3. Link generation events to an artifact only when an artifact is actually created from that output.
4. Add explicit contribution hooks for other existing generation adapters; otherwise expose only the documented event API.
5. Add tests for normal provider success, fallback success, no-provider outcome, provider failure, and unknown attribution.

**Acceptance:** provenance never claims Smart BethG itself generated output from an external model and never records an attempted-but-unsuccessful model as the successful contributor.

### Unit 5 — Human contribution, review, and approval
1. Add explicit human contribution and approval event schemas.
2. Add user-editable attribution summaries and optional prompt/instruction inclusion.
3. Record source asset references and their hashes.
4. Add tests proving approvals are explicit, owner-bound, timestamped, and cannot be inferred from passive access.

**Acceptance:** human and AI contributions are represented separately and optional sensitive instruction text is not stored by default.

### Unit 6 — Portable manifest and cryptographic signing
1. Generate deterministic, versioned JSON manifests from the verified event stream.
2. Add Ed25519 signing and public-key verification using a maintained cryptography dependency already present or explicitly added after dependency review.
3. Add key IDs, trust labels, key-rotation compatibility, and clear unsigned/unverifiable states.
4. Sign the manifest digest and bind it to the asset hash and event-chain head.
5. Add tampering, missing-key, wrong-key, changed-asset, changed-manifest, and signature-round-trip tests.

**Acceptance:** an exported manifest is deterministic; a configured public key verifies a valid signature; any changed asset/manifest/event chain fails; missing keys never produce a green verification result.

### Unit 7 — C2PA library evaluation and compatible export
1. Evaluate maintained C2PA SDK/library support for Python/runtime, supported media types, signing certificate handling, and independent validation.
2. Record the selected library and version in this plan before adding it.
3. Map supported provenance fields into C2PA assertions/actions/ingredients.
4. Generate C2PA manifests only through the real library and validate output with an independent validator where possible.
5. Keep the internal manifest export available even if C2PA support is blocked.
6. Add positive and negative interoperability tests and explicit trust-status labels.

**Acceptance:** any file labelled C2PA is produced by a real compatible implementation and passes validation; otherwise the feature reports C2PA export as unavailable and does not mislabel the sidecar JSON.

### Unit 8 — Export, verification, deletion, and UI integration
1. Add manifest-only and asset-plus-manifest export paths.
2. Add verification results with clear pass/fail/unverifiable reasons.
3. Create a focused Asset Library/Provenance page because the inspected main branch has no existing artifact-library/detail screen. Include upload, asset list, provenance summary, timeline, and verification/export actions; link it from existing navigation without redesigning unrelated screens.
4. Integrate permitted provenance records into account export.
5. Implement documented deletion/retention behavior and tests.
6. Add accessibility, responsive, loading, empty, and error states for the new UI.

**Acceptance:** users can inspect, export, and verify provenance; deletion/export behavior matches privacy rules; existing artifact and chat workflows remain functional.

### Unit 9 — Final security and regression verification
1. Run focused unit and route tests after each unit.
2. Run the full documented test suite against a disposable PostgreSQL test database.
3. Run Python compilation, lint/type checks if configured, JavaScript syntax checks if touched, dependency audit, and secret scanning as configured.
4. Run migration clean-install and upgrade tests.
5. Review access control, upload handling, key handling, hash-chain integrity, export privacy, deletion, and error responses.
6. Record exact commands, results, skipped tests, and environmental limitations.

**Acceptance:** every requirement maps to fresh verification evidence. No production readiness, official C2PA trust, legal approval, or deployment is claimed.

## 11. Test matrix

Required regression coverage includes:

- Artifact ownership and storage isolation.
- Text artifact compatibility.
- Binary upload limits and content-type/signature mismatch.
- SHA-256 exact-byte reproducibility.
- Event sequence uniqueness and transaction concurrency.
- Hash-chain tampering and reordering detection.
- Idempotent event creation.
- AI provider actual-success attribution and fallback attribution.
- No-provider/provider-failure records not mislabelled as generated output.
- Human approval explicitness and actor identity.
- Prompt/instruction privacy defaults.
- Manifest canonicalization and deterministic digest.
- Ed25519 valid/invalid signature, wrong key, missing key, key rotation.
- Asset, event, and manifest owner isolation.
- Export contents and secret redaction.
- Deletion and retention behavior.
- C2PA interoperability only if the SDK unit is completed.
- Existing artifact API and chat behavior regression.

## 12. Delivery and release boundaries

- Work only on `feat/asset-provenance-attribution-2026-11-03`.
- Do not modify `main`, merge other open pull requests, or rebase/retarget unrelated PRs.
- Commit this plan before source implementation.
- Implement one unit at a time, keeping commits reviewable.
- Do not push to production, deploy, configure live signing secrets, or publish a release.
- Open a draft PR against `main` only after implementation and verification, unless the user directs otherwise.
- Do not force-push.
- Preserve unrelated repository work.

## 13. Completion record

| Unit | Status | Commit / evidence |
|---|---|---|
| 0 — Baseline | Complete | Main baseline `b8b632d`; plan commit `a4edb28`; repository/API/storage/migration map recorded. Focused tests deferred to disposable-PostgreSQL CI. |
| 1 — Schema and contracts | Complete | Migration `0012_asset_provenance.sql`; contracts/repository and DB registration committed. New provenance tests: 9 passed. Compile: passed. PostgreSQL integration: passed. Full suite: 351 passed, 7 unrelated existing failures, 9 skipped (approval legacy routes, consent/CSRF/session fixtures, workspace auth fixtures); see CI run `41677453908`. |
| 2 — Binary asset support | Pending | |
| 3 — Event service and API | Pending | |
| 4 — AI attribution | Pending | |
| 5 — Human contribution | Pending | |
| 6 — Manifest and signing | Pending | |
| 7 — C2PA export | Pending | |
| 8 — Export, verification, deletion, UI | Pending | |
| 9 — Final verification | Pending | |

**Final completion rule:** this feature is complete only when the acceptance criteria and verification evidence for every applicable unit are recorded above. A unit blocked by a real dependency or environment limitation must be marked blocked, not complete.
