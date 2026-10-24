# Smart BethG Storage Adapters

## Modes

Smart BethG supports two configured storage modes for uploaded files and generated artifacts:

- `local` (default): stores objects beneath `SMART_BETHG_STORAGE_ROOT`. Use for local development and a single application instance with durable disk.
- `s3`: stores objects in an S3-compatible bucket. Use this for shared durable object storage when deploying multiple application instances.

Set `SMART_BETHG_OBJECT_STORAGE=s3` and `SMART_BETHG_S3_BUCKET=your-bucket`. Optional settings are `SMART_BETHG_S3_PREFIX` (defaults to `smartbethg`), `SMART_BETHG_S3_REGION` (defaults to `us-east-1`), and `SMART_BETHG_S3_ENDPOINT_URL` for S3-compatible providers. Credentials must be supplied through the host's secret manager or the standard AWS credential chain; never commit keys or put them in browser-visible configuration.

## Safety and deployment

Every database lookup remains owner-scoped before an object locator is read or deleted. The S3 adapter validates the bucket and the namespace/owner key prefix. Do not expose object keys as authorization: application authentication and ownership checks remain mandatory. Bucket access should be private, with least-privilege credentials and encryption at rest enabled by the provider.

The adapter currently covers uploaded files and generated artifacts. Other workspace paths and filesystem-backed features still need an inventory and migration before the application can be considered multi-instance ready. Before scaling, run a cross-instance write/read/delete test, verify file deletion and orphan cleanup, test permissions with two different users, and rehearse backup/recovery. Existing local-path records are not automatically migrated into S3; plan and verify a controlled copy plus locator update before switching a deployment with existing files.

## Failure behavior

Storage errors are returned as controlled service errors or logged with user/file identifiers; raw provider credentials and private object content must not be written to logs. Database rows are removed before best-effort object deletion so a stale object is preferable to a live row pointing at missing data. A periodic orphan-cleanup process remains future work.
