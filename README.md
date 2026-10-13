# Smart BethG

**Status:** Active development — not yet cleared for unrestricted public launch.  
**Last updated:** 2026-10-10 UTC. See [the decision log](docs/DECISION_LOG.md) and [architecture decisions](architecture.md) for dated records.

Smart BethG is an AI-assisted agent workspace with chat, provider routing, memory, file/knowledge features, and security-governed tools. The repository is being prepared for a public launch, but several security, product, and operational release gates remain open. Do not expose unrestricted registration or sensitive production data until those gates are verified.

## Architecture decisions

- **Application database:** PostgreSQL is required in local development, tests, and production. The app has no SQLite fallback; SQLite is accepted only as a read-only source by the explicit legacy migration utility.
- **Scaling:** one or multiple application instances use the same PostgreSQL database. Authentication rate-limit events are shared through the database.
- **Files and workspaces:** local storage works for development and single-instance testing. Multiple instances require a shared durable storage mount for uploads, generated artifacts, and workspaces. PostgreSQL does not share local files between replicas.
- **Hosting:** provider-neutral Python/ASGI application. No Render-specific manifest, API, or runtime is required. Deploy to any compatible Linux/Python host that can provide PostgreSQL and durable storage.
- **Security:** registration is closed by default. Training export is disabled until opt-in consent controls exist. High-risk tool actions require approval. Unsandboxed host Python execution is disabled in production.

## Requirements

- Python 3.12 (see `.python-version`)
- PostgreSQL for every environment (local development, tests, and production)
- A writable storage root; for multiple app instances, it must be a shared durable mount
- At least one AI provider API key for live model responses (provider selection otherwise reports that no provider is configured)

## Local development

PostgreSQL can run locally; you do not need a hosted database to develop Smart BethG. The repository includes a Docker Compose service for a local-only PostgreSQL 16 instance. Install Docker Desktop (Windows/macOS) or Docker Engine with the Compose plugin (Linux), then start the database from the repository root:

```bash
docker compose up -d postgres
```

The compose file binds PostgreSQL to localhost only and uses credentials intended for local development. Never use those credentials in production. To stop the service without deleting its database volume, run `docker compose stop postgres`. To permanently remove the local database volume, `docker compose down -v` deletes its data; use that only when you intentionally want a fresh local database.

Create and activate a Python virtual environment, then install dependencies:

```bash
python -m venv .venv
python -m pip install -r requirements.txt -r requirements-dev.txt
```

Set the local PostgreSQL URL before starting the app. On PowerShell:

```powershell
$env:DATABASE_URL = "postgresql://smartbethg:local_dev_only_change_me@localhost:5432/smartbethg_dev"
$env:SMART_BETHG_ENV = "development"
uvicorn main_fastapi:app --host 127.0.0.1 --port 8000
```

On Bash:

```bash
export DATABASE_URL="postgresql://smartbethg:local_dev_only_change_me@localhost:5432/smartbethg_dev"
export SMART_BETHG_ENV=development
uvicorn main_fastapi:app --host 127.0.0.1 --port 8000
```

The application initializes the PostgreSQL schema through the numbered files in `migrations/postgresql/`. If `DATABASE_URL` is missing or points to SQLite, the app fails clearly instead of creating or using a second database. Keep local development data separate from production data.

### Run tests locally

Use a separate PostgreSQL database for tests. Create it once:

```bash
docker compose exec postgres createdb -U smartbethg smartbethg_test
```

PowerShell:

```powershell
$env:SMART_BETHG_ENV = "test"
$env:SMART_BETHG_SECRET_KEY = "local-test-only-not-for-production"
$env:DATABASE_URL = "postgresql://smartbethg:local_dev_only_change_me@localhost:5432/smartbethg_test"
$env:SMART_BETHG_TEST_DATABASE_URL = $env:DATABASE_URL
python -m unittest discover -s tests -p "test_*.py" -v
```

Bash:

```bash
export SMART_BETHG_ENV=test
export SMART_BETHG_SECRET_KEY="local-test-only-not-for-production"
export DATABASE_URL="postgresql://smartbethg:local_dev_only_change_me@localhost:5432/smartbethg_test"
export SMART_BETHG_TEST_DATABASE_URL="$DATABASE_URL"
python -m unittest discover -s tests -p "test_*.py" -v
```

The shared test base creates a unique PostgreSQL schema per test and drops it afterward. The test database must be disposable; never set these variables to a production database. The dedicated PostgreSQL integration tests are enabled separately with `SMART_BETHG_RUN_POSTGRES_TESTS=1` and should run only against a disposable PostgreSQL instance.

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
