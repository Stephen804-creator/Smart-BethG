# Artifact Storage and Migration Runbook

**Created:** 2026-10-10 UTC  
**Last updated:** 2026-10-10 UTC  
**Scope:** Generated files and artifact objects; independent from the deployment provider.

## Supported backends

- local: intended for local development and single-instance testing. Configure with SMART_BETHG_OBJECT_STORAGE_BACKEND=local (the default).
- s3-compatible: intended for production and shared access across multiple app instances. Configure SMART_BETHG_OBJECT_STORAGE_BACKEND=s3-compatible, SMART_BETHG_S3_BUCKET, and optionally AWS_REGION and SMART_BETHG_S3_ENDPOINT_URL. The AWS SDK credential chain is used; prefer workload/instance roles or a secret manager over hard-coded credentials.

S3-compatible storage can target AWS S3, DigitalOcean Spaces, MinIO, or a compatible service. The app core does not depend on Render.

## Important migration warning

Changing the backend variable does not copy existing local files. Do not switch a production database from local storage to S3-compatible storage until the source directory is available and a migration has been rehearsed. A database row pointing to a local path will not magically become an S3 object.

The script scripts/migrate_artifacts_to_object_storage.py defaults to a read-only dry run. It verifies local ownership boundaries and SHA-256 checksums. Run it against a copy first, then with --apply; it uploads and reads each object back before changing the PostgreSQL locator. Keep local files until you have independently verified the migrated artifacts and backup.

Example deployment environment:
- SMART_BETHG_OBJECT_STORAGE_BACKEND=s3-compatible
- SMART_BETHG_S3_BUCKET=<your-private-bucket>
- AWS_REGION=<bucket-region>
- SMART_BETHG_S3_ENDPOINT_URL=<optional-endpoint-for-compatible-storage>

Never place secret access keys in source control or commit them to a deployment file.

## Required production bucket controls

- Keep the bucket private; no public-read ACLs or public bucket policy.
- Enable provider-side encryption and TLS in transit.
- Restrict the app identity to the required bucket/prefix actions.
- Enable versioning or an equivalent recovery mechanism where available.
- Configure retention/lifecycle rules only after aligning them with the privacy policy.
- Configure independent backups and test restoration.
- Set upload, download, and generation limits; review orphan objects and failed deletions.
- Verify access isolation with two users and test missing/corrupt objects.

## Safe migration procedure

1. Take a PostgreSQL backup and a complete copy of the local artifacts directory.
2. Test the restore of both backups to an isolated environment.
3. Configure the S3-compatible target credentials in the isolated environment.
4. Run the migration script without --apply and review every artifact and checksum error.
5. Run with --apply against the isolated environment.
6. Read each migrated artifact through the application and compare its SHA-256.
7. Test delete, owner isolation, restart, and a second app instance.
8. Only after acceptance, schedule a maintenance window and repeat against production.
9. Retain the source backup and local directory until a documented rollback window has passed.
10. Do not use --delete-local-after-copy until post-migration verification and independent backup restoration have succeeded.

## Multi-instance requirements

PostgreSQL plus S3-compatible artifact storage is necessary but not sufficient for multi-instance execution. User workspaces, uploaded files, generated media, and background job state must all be shared or accessed through an explicit remote worker/service. Do not scale replicas while any required runtime data remains on a replica-local filesystem.
