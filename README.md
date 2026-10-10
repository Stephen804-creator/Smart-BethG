# Smart BethG

**Status:** Active development — not yet cleared for unrestricted public launch.  
**Last updated:** 2026-10-10 UTC. See [the decision log](docs/DECISION_LOG.md) and [architecture decisions](architecture.md) for dated records.

Smart BethG is an AI-assisted agent workspace with chat, provider routing, memory, file/knowledge features, and security-governed tools. The repository is being prepared for a public launch, but several security, product, and operational release gates remain open. Do not expose unrestricted registration or sensitive production data until those gates are verified.

## Architecture decisions

- **Production database:** PostgreSQL is required. SQLite is only for local development and isolated unit tests.
- **Scaling:** one or multiple application instances use the same PostgreSQL database. Authentication rate-limit events are shared through the database.
- **Files and workspaces:** local storage works for development and single-instance testing. Multiple instances require a shared durable storage mount for uploads, generated artifacts, and workspaces. PostgreSQL does not share local files between replicas.
- **Hosting:** provider-neutral Python/ASGI application. No Render-specific manifest, API, or runtime is required. Deploy to any compatible Linux/Python host that can provide PostgreSQL and durable storage.
- **Security:** registration is closed by default. Training export is disabled until opt-in consent controls exist. High-risk tool actions require approval. Unsandboxed host Python execution is disabled in production.

## Requirements

- Python 3.12 (see `.python-version`)
- PostgreSQL for production
- A writable storage root; for multiple app instances, it must be a shared durable mount
- At least one AI provider API key for live model responses (provider selection otherwise reports that no provider is configured)

## Local development

Create a virtual environment and install dependencies:

```bash
python -m venv .venv
```

Activate it using the command for your shell, then run:

```bash
python -m pip install -r requirements.txt -r requirements-dev.txt
python -m unittest discover -s tests -p "test_*.py" -v
uvicorn main_fastapi:app --host 127.0.0.1 --port 8000
```

For local development, SQLite is used when `DATABASE_URL` is not set. Set `SMART_BETHG_ENV=test` and a test-only `SMART_BETHG_SECRET_KEY` when running tests manually if needed. Do not reuse production secrets or production databases in tests.

## Production environment

Set these variables in the hosting provider's secret/configuration manager:

- `SMART_BETHG_ENV=production`
- `DATABASE_URL=postgresql://...` — use the database provider's TLS-enabled connection URL when available.
- `SMART_BETHG_SECRET_KEY` — generate a long random secret; never commit it.
- `SMART_BETHG_SESSION_HTTPS_ONLY=true`
- `SMART_BETHG_REGISTRATION_OPEN=false`
- `SMART_BETHG_STORAGE_ROOT=/absolute/path/to/durable/storage`
- `SMART_BETHG_ALLOWED_ORIGINS` — comma-separated exact browser origins only if a separate frontend origin needs CORS.
- Provider API keys as needed: `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `GOOGLE_API_KEY`, `GROQ_API_KEY`, `OPENROUTER_API_KEY`.

Start command:

```bash
uvicorn main_fastapi:app --host 0.0.0.0 --port ${PORT:-8000}
```

The process must have write access to `SMART_BETHG_STORAGE_ROOT`. Do not use an ephemeral filesystem for user uploads or workspaces. Before multi-instance mode, mount the same durable/shared storage at the same configured path for every replica and verify that each replica sees the same test file. The service must not be scaled horizontally until that test and background-job safety checks pass.

Generate a secret locally with:

```bash
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

Never paste the generated value into source code or commit history.

## Initial administrator

Registration is intentionally closed by default. After setting up the production PostgreSQL database, create the first administrator from a trusted terminal:

```bash
python scripts/manage_user.py create-admin
```

The command prompts for a username and password. Run it only in a trusted environment connected to the intended database. It does not print the password. Keep administrator access limited and enable multi-factor authentication before public launch once the feature is implemented.

## SQLite to PostgreSQL migration

PostgreSQL schema changes are applied through ordered SQL files in `migrations/postgresql/`, tracked in `schema_migrations`. The initial baseline migration is idempotent to support a controlled adoption of the previous initializer; future changes must be added as new numbered migrations. CI verifies the baseline on a fresh PostgreSQL service, but upgrades from real prior production schemas still require rehearsal.

The repository also includes a fail-closed SQLite-to-PostgreSQL data migration utility:

```bash
DATABASE_URL="postgresql://..." python scripts/migrate_sqlite_to_postgres.py /path/to/smart_bethg.db --dry-run
DATABASE_URL="postgresql://..." python scripts/migrate_sqlite_to_postgres.py /path/to/smart_bethg.db \
  --old-storage-root /old/storage/root \
  --new-storage-root /new/storage/root
```

First take a backup and test against a fresh PostgreSQL database. The script refuses to merge into non-empty target tables and leaves the SQLite source unchanged. It migrates database rows, not uploaded files or workspace directories; copy those files separately. Use the storage-root options when the destination path differs so recognized file paths can be remapped. Follow the full [migration runbook](docs/DATABASE_MIGRATION_2026-10-10.md) and verify every migrated feature before moving real user data. Do not run this against your only production database without a verified backup.

## Legal and privacy preparation

The Terms of Service and Privacy Policy under `docs/` are **drafts, not final or approved legal documents**. Read [the dated legal/privacy launch checklist](docs/LEGAL_AND_PRIVACY_LAUNCH_CHECKLIST_2026-10-10.md) before preparing a public launch. The product owner can prepare initial drafts, but qualified Nigerian legal review is recommended before publication. Assess any NDPC registration, audit, or notification duties against the actual data-processing activities and current rules; do not assume the draft itself establishes compliance.

## Tests and CI

GitHub Actions runs:
- Python compilation and the unit test suite on SQLite.
- PostgreSQL integration smoke tests against a disposable PostgreSQL service.

A passing CI run covers only the tests that ran. It is not a penetration test, load test, accessibility review, legal review, or live-host backup/restore verification.

## Current limitations and launch gates

See [the dated whole-codebase audit](docs/WHOLE_CODEBASE_AUDIT_2026-10-10.md). Current open items include broader PostgreSQL regression coverage and rehearsed upgrades from prior schemas; shared object storage for multiple instances; a durable isolated job runner; a finished user-facing workspace for the capability APIs; password recovery and account-management flows; account data export/deletion; CSP/CSRF adversarial verification; independent tool-security review; legal review; monitoring/load tests; and backup/restore drills. Server-side session-version checks now invalidate copied signed cookies after logout, with regression tests; confirm the current CI run before merging. The approval execution path, database-backed rate limiting, per-user/global usage budgets, dependency audit, secret scan, and core PostgreSQL smoke tests have implementation and CI coverage, but still require deeper production validation.

## Security reporting

Do not include API keys, passwords, session cookies, private user data, or unredacted logs in public issues. Report security-sensitive findings privately to the repository owner.
