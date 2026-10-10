# Smart BethG Decision Log

**Maintained:** 2026-10-10 UTC  
**Timestamp rule:** Each entry carries its recorded date. The exact time and author are preserved by the corresponding Git commit timestamp. New decisions are appended; superseded decisions are marked superseded rather than silently rewritten.

## 2026-10-10 — Public launch is the product target
**Status:** Active  
Smart BethG is being engineered for a public launch. Personal/small-group operation may be used during development, but it is not the intended product boundary. Public registration stays closed until the security and privacy release gates pass.

## 2026-10-10 — PostgreSQL is required in production
**Status:** Active  
PostgreSQL is the production database for both single-instance and multi-instance deployments. SQLite is permitted only for local development and isolated tests. The production app must fail fast when DATABASE_URL is missing or not PostgreSQL. This avoids building against SQLite and later having to replace the database architecture.

## 2026-10-10 — Rate limiting must be shared
**Status:** Active  
Authentication rate-limit counters are stored in the database, not only in process memory. PostgreSQL advisory locks serialize attempts for the same hashed key across replicas. A dedicated shared limiter may be considered later for very high traffic, but no production instance may rely on independent per-process counters.

## 2026-10-10 — Single and multiple app instances share one architecture
**Status:** Active, with remaining work  
Use shared PostgreSQL in both modes. Before enabling multiple app replicas, implement shared object storage for uploads/artifacts/workspace files and durable, idempotent background jobs. A shared database does not make a local filesystem shared.

## 2026-10-10 — Approval should resume the original operation
**Status:** Required; implementation incomplete  
Approval is not just a notification or database status. The application must persist the exact pending operation, owner, action, resource, and arguments; on approval it must revalidate authorization and execute the same operation once; rejected, expired, modified, or duplicate attempts must not execute. Crash recovery must avoid blindly repeating destructive side effects. The requirement remains open until an end-to-end test proves it.

## 2026-10-10 — Build planned schema-backed capabilities
**Status:** Active  
Missions, workflows, artifacts, social content, projects, research, evidence, files, memory, and logs are intentional product areas. They are not to be left as unused tables. Implement each as a tested vertical slice (data model/repository, service, authenticated owner-scoped API, UI, audit where relevant, and tests) before advertising it as available.

## 2026-10-10 — Deployment-provider neutrality
**Status:** Active  
Render may be used as an inexpensive test target, but the application must not depend on Render-specific YAML, service types, environment assumptions, or APIs. Keep deployment configuration portable across a generic Linux/Python ASGI host, DigitalOcean, AWS, Azure, and compatible providers.

## 2026-10-10 — Legal and consent work starts now
**Status:** Active  
Draft Terms of Service and Privacy Policy now, during development, and obtain qualified legal review before public launch. Training-data use must be opt-in, recorded, and revocable; admin access is not consent. Until that consent system exists, training export remains disabled.

## 2026-10-10 — Documentation timestamps
**Status:** Active  
Architecture decisions, audit reports, migration plans, release gates, and legal drafts must carry a date/last-updated field. Changelog entries should include dates and link to the relevant commits or PR. Git commit timestamps are the precise source of truth; never invent a correction history after the fact.
