# SQLite to PostgreSQL Migration Runbook

**Created:** 2026-10-10 UTC  
**Status:** Procedure draft; run against a disposable copy before any production migration.  
**Source of exact timestamps:** Git commit history.

## Purpose

PostgreSQL is the only database engine the Smart BethG application opens in every environment. This runbook describes a one-way copy from a legacy SQLite database into a fresh PostgreSQL database without deleting or modifying the SQLite source. SQLite remains in this procedure only as a legacy import format.

## Before migration

1. Stop writes to the source application or take a consistent SQLite backup using SQLite's backup mechanism.
2. Record the source commit, source database path, storage root, file count, and database file checksum.
3. Copy the source storage directory (uploads, projects/workspaces, artifacts, memory and other file-backed data) to a safe migration workspace.
4. Create a fresh PostgreSQL database and set `DATABASE_URL` to its TLS-enabled connection string. Do not point the migration tool at a database with user data.
5. Install dependencies from `requirements.txt` and `requirements-dev.txt`.
6. Initialize the target schema:
   ```bash
   DATABASE_URL="postgresql://..." python -c "from database import initialize_database; initialize_database()"
   ```
7. Take a backup of the empty target schema if required by your operating process.

## Preview

Run a dry run first:

```bash
DATABASE_URL="postgresql://..." python scripts/migrate_sqlite_to_postgres.py /path/to/smart_bethg.db --dry-run
```

The script reports row counts and refuses to copy into a target table that already contains rows. Review counts and the source/target schema before proceeding.

## File-path remapping

Database migration does not copy uploaded files or workspaces. Copy the old storage directory separately while preserving its relative structure. If the old and new roots differ, provide both roots so stored file paths can be updated:

```bash
DATABASE_URL="postgresql://..." python scripts/migrate_sqlite_to_postgres.py /path/to/smart_bethg.db \
  --old-storage-root /old/storage/root \
  --new-storage-root /new/storage/root
```

The path remapper only changes recognized path columns whose values fall under the supplied old root. Inspect tables containing file paths before production migration; do not assume every future artifact type is covered automatically.

## Execute

```bash
DATABASE_URL="postgresql://..." python scripts/migrate_sqlite_to_postgres.py /path/to/smart_bethg.db \
  --old-storage-root /old/storage/root \
  --new-storage-root /new/storage/root
```

The script leaves the SQLite source unchanged and uses a PostgreSQL transaction for row copying. If it fails, inspect the error, preserve the source, and use a fresh empty target for a retry. Do not make the script silently skip conflicts.

## Verification checklist

- [ ] Source and target row counts match for every migrated table (excluding ephemeral rate-limit events).
- [ ] Sequence values are advanced past existing numeric IDs.
- [ ] Login, session creation, conversation list/history, files, memory, knowledge retrieval, approvals, audits, and tasks work against PostgreSQL.
- [ ] Every owner-scoped API denies cross-user access.
- [ ] File downloads, text extraction, and deletion work after storage-path remapping.
- [ ] A sample pending approval resumes its saved operation once; duplicate execution is rejected.
- [ ] Rate limits are shared across two app processes using the same PostgreSQL database.
- [ ] Backups are taken independently and a restore is tested in a separate database/storage location.
- [ ] The deployment is restarted and redeployed; records and files remain available.
- [ ] The rollback plan is documented. Keep the original SQLite file and file backup until sign-off.

## Important limitations

- This is a data-copy utility, not a general schema-migration framework. Review it against the exact source and target schema versions.
- It does not copy or decrypt secrets held only in process memory.
- It does not copy rate-limit events; these are intentionally ephemeral.
- It does not automatically discover every possible file path in future schemas.
- A green smoke test does not prove every query is PostgreSQL-compatible.
- Do not delete the SQLite source or declare migration complete until all verification items have evidence and an operator signs off.
