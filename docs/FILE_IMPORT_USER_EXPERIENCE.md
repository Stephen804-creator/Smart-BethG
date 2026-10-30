# File Import — User Experience and Operational Trade-offs

Status: product/engineering contract; no UI implementation.
Date: 2026-10-30

## User-facing principle

Security work should be automatic and mostly invisible. Users should upload a file once, continue working, and see a clear status only when a check is still running or needs their attention. Do not make users choose antivirus settings, understand MIME types, or manually approve routine safe files.

## Recommended user journey

1. User selects a file and uploads it once.
2. Smart BethG confirms receipt and stores the original bytes in private quarantine storage.
3. A background inspection service checks the file. The upload request should not wait for slow scanning or document parsing.
4. Once inspection passes, Smart BethG makes the file available in the user's normal project/file area. If inspection rejects it, preserve a clear reason and allow deletion/replacement.
5. Only when the user explicitly asks to import/extract/execute content does the corresponding processing pipeline run. Uploading a project must never run its code.

Suggested user-facing statuses: Uploading → Received / Checking → Ready → Needs attention / Could not check. Avoid exposing internal scanner names, signatures, infrastructure errors, or security jargon.

## Recovery and accessibility

- A scanner outage should not destroy an upload. Keep the original safely quarantined, show "Checking is delayed; your upload is saved", and retry automatically with bounded backoff.
- Do not tell a user an upload is safe when the scanner is unavailable or its result is indeterminate.
- Do not require repeated upload attempts after a temporary scanner outage.
- Preserve the original filename for display, but use server-generated object identifiers internally.
- Provide a clear delete/retry action and do not silently discard files.
- Keep status polling lightweight; prefer notifications or bounded polling rather than rapid repeated requests.
- Make status text accessible to screen readers and avoid relying on color alone.
- Do not reveal scanner internals or malware signatures to ordinary users.

## Trade-offs

| Trade-off | User impact | Mitigation |
|---|---|---|
| Quarantine before use | A file may not be immediately usable | Fast background inspection; show progress and allow other work to continue |
| Scanner outage | File stays pending instead of becoming available | Retain upload; retry; communicate delay; never falsely mark clean |
| File-type allowlist | Some uncommon formats may be rejected | Publish supported formats and provide a safe alternative/extension request |
| Size and rate limits | Very large or repeated uploads are rejected/throttled | Explain limits before upload; configurable plan limits; resumable uploads later |
| Archive inspection | ZIP imports can take longer | Separate inspection job; bounded progress; never execute automatically |
| Storage and scanning cost | More infrastructure/storage and some added latency | Stream uploads, cap resources, retention for abandoned quarantine, measure cost |
| False positives | A legitimate file may be blocked | Safe appeal/retry path and operator review; do not silently delete it |
| Extra system components | More operational complexity | Keep interfaces modular; start with one managed scanner/worker, not a microservice per file type |

## Privacy and retention

Quarantine is private user data, not a public moderation queue. Enforce owner/workspace authorization, encrypt storage and transport, avoid logging file contents, and define retention for pending/rejected uploads. Do not use uploaded content for model training or agent context merely because it was scanned.

## Current implementation boundary

The current branch implements bounded upload intake, private quarantine storage, metadata/checksum recording, owner-scoped status listing/deletion, basic type/signature checks, and request-body caps on both legacy and versioned upload routes.

It does not yet provide background antivirus scanning, automatic release, isolated archive extraction, or an isolated document parser. The API must therefore not describe current uploads as scanned/clean or make them available for extraction or execution. The next implementation slice must add a separately deployed scanner/inspection worker and durable retry/status handling before a user-facing "Ready" state is offered.

The ASGI body cap is per application process, not a global cross-replica quota. Production ingress must also enforce a request-body limit, and production load tests must account for the middleware's bounded in-memory buffering.
