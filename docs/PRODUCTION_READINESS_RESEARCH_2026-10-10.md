# Smart BethG — Production Readiness Research and Delivery Roadmap

**Created:** 2026-10-10 UTC  
**Last updated:** 2026-10-10 UTC  
**Status:** Research and planning baseline; not a production certification  
**Repository:** `Stephen804-creator/Smart-BethG`  
**Base reviewed:** merged PR #1, merge commit `f80173c8d294632e8ff102bfce1139d6e0b1863a`  
**Verification snapshot:** the merge commit's GitHub Actions test workflow completed successfully. The merged PR records 317 passing unit tests, 9 PostgreSQL-only tests, Python compilation, dashboard JavaScript syntax checking, dependency auditing, and secret scanning. This is a test baseline, not proof of a safe public launch.

## 1. Executive assessment

Smart BethG has made meaningful progress toward a public product: PostgreSQL is the production database, SQLite is limited to local development and unit tests, rate limiting is database-backed, approval records can resume a saved operation, registration is closed by default, workspace access is user-scoped, upload reads are bounded, CSRF protection is global, training export is disabled pending consent, and CI includes unit tests, PostgreSQL integration, dependency auditing, and secret scanning.

It is **not yet production-ready for unrestricted public registration**. The most important remaining gaps are shared durable file/workspace storage for multiple instances, durable background execution and crash recovery, broader PostgreSQL migration/query coverage, password recovery and full account-data lifecycle, CSP enforcement, browser and accessibility testing, independent adversarial security review, operational monitoring and recovery drills, and legal/privacy review aligned to the actual data flows.

The strategy should be to make one architecture work for one instance and many instances, rather than build a single-instance product and later replace core systems. PostgreSQL remains the shared production database in both modes. Scaling horizontally must be gated by shared storage and safe worker execution, not by changing databases later.

## 2. Product definition: decide the first customer before building every feature

The current repository describes Smart BethG as a multipurpose AI agent. That is a technology description, not a sufficiently sharp customer promise.

### Proposed initial positioning to validate

**Smart BethG is a user-controlled AI work agent that helps individuals and small teams organize projects, work with their files and knowledge, plan tasks, and execute approved actions through a transparent, auditable workflow.**

This positioning is a hypothesis, not a market fact. Validate it with interviews and a working prototype before committing to a large marketing budget.

Potential customer groups:
1. Independent developers and technical students who need project context, coding assistance, repository workflows, and repeatable task execution.
2. Freelancers and small service businesses who need research, document handling, project tracking, and controlled automation.
3. Content creators who need research, drafts, reusable workflows, and social-content organization.
4. Small teams that need shared projects, permissions, audit history, and cost controls.

Do not try to launch equally for all four groups. Interview at least 10–15 people across these groups, ask them to demonstrate a real recurring task, identify what they currently use, and ask what they would pay to solve it. Choose one beachhead segment based on repeated pain, ability to reach the user, risk level, and willingness to pay.

### Product promise and trust boundary

Smart BethG should not promise “an AI that can do anything.” Promise reliable work on explicitly supported tasks, with:
- clear plan and current status;
- explicit permissions and approval for consequential actions;
- a record of what was requested, what ran, what changed, and what failed;
- user control over memory, files, data export/deletion, and provider selection;
- predictable usage limits and cost visibility;
- clear separation between a draft/record and an executed operation.

A mission record is not a running mission. A workflow editor is not a workflow engine. A social-content draft is not publication. A button or table must not imply functionality that is not implemented and tested.

## 3. Whole-team responsibility map

One founder can temporarily wear several hats, but every responsibility needs an owner, deliverable, and acceptance criteria. Do not use role names as decoration: each role should create evidence that a release decision can rely on.

### A. Full-stack developer

Owns vertical slices from UI to API to database:
- implement projects, missions, workflows, files, artifacts, knowledge, and social-content capabilities end to end;
- keep API schemas and UI behavior consistent;
- add validation, loading/error/empty states, accessible controls, and tests;
- ensure each record is scoped to its owner or authorized team;
- remove dead links, placeholder buttons, misleading labels, and unused schema only after checking references and migrations.

Definition of done: a user can complete a documented scenario from the UI; server-side authorization protects every object; database changes use versioned migrations; automated tests cover success, invalid input, failure, and cross-user access.

### B. System / solution architect

Owns the system boundaries and decision records:
- maintain C4-style context, container, and critical component diagrams;
- define API contracts, data ownership, trust boundaries, failure modes, and threat models;
- preserve PostgreSQL as production storage for single and multi-instance deployment;
- separate the web/API process from durable job workers and external-provider adapters;
- document where state lives: PostgreSQL, shared object storage, ephemeral local disk, cache, and provider systems;
- review each new subsystem for idempotency, retry behavior, timeouts, data retention, and portability.

Definition of done: important decisions have a dated record, alternatives, consequences, and a testable implementation plan. The architecture must not depend on a specific hosting provider.

### C. Security and data privacy specialist

Owns security design, privacy governance, and independent review:
- build and maintain a threat model and data-flow inventory;
- review authentication, session revocation, CSRF, CORS, SSRF, uploads, tool execution, secrets, and ownership checks;
- map security tests to OWASP ASVS and the OWASP API Security Top 10;
- enforce least privilege for tools, integrations, background workers, and administrators;
- review data retention, deletion, export, consent, incident response, and subprocessors;
- coordinate an independent penetration test before unrestricted public registration.

Definition of done: high-risk controls have evidence and repeatable tests; findings are triaged by severity; unresolved critical/high risks block launch or require a documented, time-bounded exception approved by the responsible owner.

### D. QA engineer / tester

Owns evidence that the product works and fails safely:
- build a requirements-to-tests traceability matrix;
- test API contracts, user flows, ownership isolation, permissions, error handling, and migration upgrades;
- add browser end-to-end tests for signup/login, projects, files, missions, approvals, data export/deletion, and recovery;
- test concurrency, rate limits, spending limits, retries, duplicate actions, cancellation, and process crashes;
- run accessibility checks and supported-device/browser tests;
- create reproducible bug reports with expected/actual behavior, environment, steps, severity, and evidence.

Definition of done: no release blocker is open; all critical user journeys have automated coverage; manual exploratory testing has a dated record; CI results correspond to the exact release commit.

### E. Backend developer

Owns domain logic and reliable execution:
- enforce PostgreSQL-compatible SQL and migration discipline;
- use transactions for state transitions, budgets, approvals, and idempotency;
- add durable jobs with leases, bounded concurrency, retries, cancellation, and crash recovery;
- implement password reset/recovery, user data export/deletion, audit events, and provider usage/cost accounting;
- make external calls timeout-bounded and retry only when safe;
- return stable API errors and document versioning/deprecation.

Definition of done: every mutation is authenticated, authorized, validated, transactionally safe where needed, observable, and tested under failure conditions.

### F. Frontend / mobile developer

Owns the experience across screens and devices:
- create consistent responsive layouts and accessible components;
- provide project/workspace, files/artifacts, mission/job status, approval, knowledge/memory, usage/billing, and account/privacy screens;
- make queued/running/succeeded/failed/cancelled/needs-approval states visible;
- support keyboard navigation, visible focus, screen-reader labels, reduced motion, readable text, and meaningful empty/error states;
- ensure CSRF tokens and session behavior work across all state-changing requests;
- test Android-sized viewports first, plus desktop and major mobile browsers.

Definition of done: no screen suggests a fake capability; critical flows work without a mouse; errors are understandable; the interface stays usable on small screens and slow networks.

Mobile native apps should follow only after the web/API contracts are stable. A responsive web app/PWA is a lower-cost first step than maintaining separate native clients before product-market fit.

### G. Product manager / product owner

Owns the user problem, priorities, and launch scope:
- choose the initial customer segment and core job-to-be-done;
- maintain a prioritized backlog with acceptance criteria and explicit non-goals;
- run user interviews and usability sessions;
- define activation, task-success, retention, reliability, support, and cost metrics;
- prevent features from being advertised before they work;
- run a launch-readiness review and maintain a public changelog/known-limitations page.

Definition of done: every sprint has a measurable customer outcome, and each release is tied to feedback or a validated risk reduction.

### H. UI/UX designer

Owns the interaction model and trust:
- map first-run onboarding and first successful task;
- design the plan → review → approval → execution → result flow;
- distinguish suggestions, drafts, saved records, queued jobs, running jobs, and completed actions;
- explain permissions and the exact scope of each approval;
- design privacy controls, memory management, cost visibility, failure recovery, and destructive-action confirmations;
- conduct usability testing and an accessibility audit.

Definition of done: target users can understand what the system will do, what it already did, what it costs, and how to stop or undo it where possible.

### I. DevOps / cloud engineer

Owns repeatable deployment and operations:
- keep the application portable across compatible Linux/Python ASGI hosts; do not couple application behavior to Render;
- define environment variables and secrets management, TLS, database connectivity, health/readiness checks, migrations, rollback, and deploy procedure;
- configure PostgreSQL backups, point-in-time recovery where supported, and restore drills;
- implement shared durable object storage before multiple app replicas;
- set up structured logs, metrics, traces, error alerts, uptime checks, resource limits, and incident runbooks;
- test deployment from a clean environment and document the cheapest safe staging configuration.

Definition of done: a release can be deployed and rolled back from documented steps; data can be restored into a clean environment; failures alert an owner; no critical secret is stored in the repository.

### J. End-user representative

Owns reality-checking:
- provide real tasks and sample data, not just opinions about features;
- identify confusing terms, missing states, and unsafe defaults;
- participate in onboarding and accessibility tests;
- report the time and number of steps needed to finish a task;
- validate that export, deletion, approval, and cost controls are understandable.

Definition of done: the core job is completed reliably by someone who did not build the application.

### K. Partner / integration owner

Owns external dependency relationships:
- document provider API limits, terms, pricing, retention, and data-processing commitments;
- define integration contracts, scopes, key rotation, webhooks, timeouts, and failure handling;
- negotiate data-processing terms where required;
- avoid promising availability or model behavior controlled by third parties;
- maintain a provider fallback and graceful-degradation policy where legally and technically feasible.

Definition of done: every integration has an owner, least-privilege credentials, documented data flow, cost limits, and an exit/replacement plan.

### L. Financial strategist

Owns unit economics and survival:
- calculate cost per successful task, not just cost per chat message;
- include model tokens, retries, search, storage, bandwidth, logs, database, email, payment fees, support, and taxes;
- track revenue per paying user, gross margin, churn, conversion, and cash runway;
- set per-user budgets and a global spending ceiling;
- model low/base/high usage and provider price changes;
- avoid unlimited plans until real usage distributions are known.

Definition of done: pricing is based on measured usage and a conservative margin model; runaway usage can be stopped automatically; paid features have clear limits and terms.

### M. Competitor and market research owner

Owns evidence, not assumptions:
- compare product promises, onboarding, supported workflows, integrations, privacy, approvals, pricing, and limitations;
- interview users of alternatives and ask what they still cannot do;
- identify a narrow differentiator users care enough to pay for;
- re-check competitor features and prices before any public pricing or positioning decision.

Definition of done: a dated competitive matrix is linked to official sources and customer interviews; differentiation is stated as a testable hypothesis.

## 4. Target architecture

### Required now

1. **API/web tier:** stateless FastAPI application; no critical cross-request state held only in process memory.
2. **Production database:** PostgreSQL for both one-instance and multi-instance deployments. SQLite is local/test only.
3. **Versioned schema migrations:** new numbered migration for every schema change; test clean install, upgrade from previous schema, and recovery/rollback procedure.
4. **Shared rate limiting and budgets:** database-backed enforcement for now; use atomic operations/locking and concurrency tests. Consider a dedicated shared limiter only if measured scale requires it.
5. **Durable jobs:** separate job state from HTTP request lifetime; persist queued/running/finished/failed/cancelled state, attempts, lease, idempotency key, timestamps, and error summary.
6. **Shared file/object storage:** use an adapter so local filesystem works for development but production storage can use an S3-compatible service or another supported object store. Store metadata and authorization in PostgreSQL, content in object storage, and verify owner access before issuing downloads.
7. **Provider adapters:** isolate AI/search/email/payment providers behind interfaces; record provider/model, latency, outcome, token use, and estimated cost without logging sensitive prompts by default.
8. **Security boundary:** centralized authentication and authorization dependencies, owner/team-scoped repositories, CSRF protection, safe CORS, input validation, rate limits, secrets handling, and auditable privileged actions.
9. **Observability:** structured logs with request/job IDs; metrics for latency, error rates, queue age, provider failures, budget rejection, and database pool saturation; alerts on actionable failures.
10. **Portable deployment:** standard ASGI entry point, environment-driven configuration, container support if useful, no provider-specific runtime assumptions.

### Single-instance and multi-instance behavior

- **Single instance:** one web process may use shared PostgreSQL and configured durable object storage. Local disk may be used only for development or explicitly disposable test data.
- **Multiple instances:** all web replicas use the same PostgreSQL, shared object storage, shared limiter/budget enforcement, and durable queue/worker model. Do not scale local workspace directories across replicas and assume consistency.
- **Worker separation:** execute risky tools in a restricted isolated worker/container with bounded CPU, memory, time, filesystem, and network access. Do not enable unrestricted host-terminal execution in the public service.
- **No premature Kubernetes:** use a simple portable deployment until measurements require orchestration. Production architecture can be multi-instance-ready without starting with a complex cluster.

## 5. Priority order

### P0 — before inviting external testers with real data

- Confirm current main branch and exact CI status.
- Run a route-by-route authentication/authorization inventory; add cross-user tests for every resource ID and every privileged route.
- Review tool execution end to end: allowlist, working directory, symlink handling, network restrictions, timeout, output limits, secrets isolation, approval binding, and audit.
- Re-run PostgreSQL tests on the current head and add repository-by-repository integration coverage.
- Confirm backup and restore from a fresh database; test schema upgrade and recovery using a disposable copy.
- Ensure no secrets or real user data are present in test fixtures/logs.
- Keep public registration closed until launch gates pass.

### P1 — before public beta

- Add shared durable object storage and storage migration procedures.
- Add durable jobs, bounded worker execution, safe cancellation, idempotency, retry policies, and crash recovery.
- Finish password recovery, session/account lifecycle, data export/deletion, and privacy settings.
- Enforce CSP after eliminating unsafe inline dependencies and reviewing report-only violations.
- Add browser end-to-end tests and accessibility audit.
- Add abuse prevention for account creation, uploads, provider spend, web research, tool execution, and automated content.
- Implement operational monitoring, alerting, support/contact process, incident response, and rollback runbook.
- Complete independent penetration test and remediate critical/high findings.

### P2 — before commercial launch

- Finalize and publish reviewed Terms of Service and Privacy Policy.
- Implement consent records and withdrawal for any optional training/model-improvement use; until complete, keep training export disabled.
- Complete pricing, payment, refunds, taxes, cancellation, and support policies if charging users.
- Add user onboarding, product documentation, status/incident page, known limitations, and changelog.
- Complete load/concurrency testing at a realistic expected workload; establish service objectives.
- Validate target segment, positioning, and pricing with interviews and paid pilots.
- Decide whether any certifications are commercially necessary; do not claim SOC 2, ISO, or other certification without a valid audit/certification.

### P3 — after launch evidence

- Add more advanced workflow templates, integrations, team collaboration, native mobile applications, and richer autonomous planning only when demand and safety evidence justify them.
- Scale infrastructure based on observed bottlenecks, not speculative traffic.
- Reassess the database-backed limiter and queue only after measured throughput/latency proves a need to replace them.

## 6. Quality and release gates

The release checklist should be a versioned document and tied to a specific commit.

### Functional
- Core flows pass end-to-end from a clean account.
- Every visible control works or is clearly marked unavailable.
- Mission records, workflow definitions, and job executions are distinct in API and UI.
- Approval resumes the same saved action exactly once, with authorization rechecked; reject/expire/duplicate attempts cannot run it.
- Errors, timeouts, cancellation, and partial failure have clear states.

### Security
- Every resource endpoint has positive and negative ownership tests.
- CSRF, cookie security, session revocation, CORS, password reset, and authentication abuse controls are tested.
- SSRF, redirects, DNS rebinding risks, path traversal, symlinks, archive bombs, upload MIME/content mismatches, shell argument injection, and Git edge cases are tested.
- Secrets are not in logs, source, images, or client bundles.
- Dependency and secret scans run on every pull request and scheduled updates.
- Independent tester receives a defined scope, safe test environment, and written authorization.

### Reliability
- PostgreSQL concurrency tests cover budget reservation, rate limiting, approvals, jobs, and idempotency.
- Database migration and backup restoration are rehearsed.
- Provider timeouts, provider 429/5xx, database outage, object-store outage, worker crash, and deploy rollback are tested.
- No request can run indefinitely or consume unbounded memory/storage.
- Observability identifies the failing dependency and affected job without exposing sensitive content.

### Privacy
- Data inventory names each data category, purpose, legal basis, recipients, retention, and deletion behavior.
- User can understand what goes to external AI/search providers.
- Account deletion/export covers conversations, files, artifacts, memory, missions, logs where legally possible, and backups according to documented retention.
- Training use is opt-in, versioned, recorded, and revocable; disabled until fully implemented.
- Published policy matches actual deployed behavior.

### UX and accessibility
- Keyboard-only use for core flows.
- Visible focus, semantic labels, useful errors, sufficient contrast, zoom/responsive behavior, and reduced-motion support.
- Test on small Android viewport and common desktop browsers.
- New users can complete first successful task without a developer explaining hidden behavior.

### Operations
- Fresh deployment from documented instructions.
- TLS/domain/health checks and alerting verified.
- Backup restore into a separate environment verified.
- Rollback rehearsed.
- Runbook names an operator/contact and first-response actions.
- Resource and spend limits are configured.

## 7. Legal, privacy, and regulatory route

**Do not treat a template as an approved legal document.** Create working drafts now, then obtain a review from a qualified lawyer familiar with technology contracts, privacy/data protection, consumer law, intellectual property, and the jurisdictions where Smart BethG will operate. The founder is responsible for ensuring the published documents accurately describe the service; counsel helps identify and draft the legal obligations. There is generally no single government office that pre-approves every startup's Terms of Service and Privacy Policy as a universal certificate of legality.

For Nigeria, begin with the official Nigeria Data Protection Act 2023 and Nigeria Data Protection Commission (NDPC) guidance. Determine whether the operator qualifies as a data controller or processor of major importance and whether registration, a Data Protection Officer, a Data Protection Compliance Organisation (DPCO), a data protection impact assessment, breach reporting, or other obligations apply to the actual scale and processing. Ask the NDPC or a licensed DPCO/qualified Nigerian privacy lawyer to assess applicability; do not assume registration is or is not required solely from the size of the codebase.

Primary starting points:
- NDPC, Nigeria Data Protection Act 2023: https://www.ndpc.gov.ng/ndp-act-2023/
- NDPC FAQs: https://ndpc.gov.ng/faqs/
- NDPC DPCO registration requirements: https://ftp.ndpc.gov.ng/dpco-registration-requirements/
- NIST Secure Software Development Framework (voluntary engineering framework): https://csrc.nist.gov/pubs/sp/800/218/final
- OWASP Application Security Verification Standard (technical security test baseline): https://owasp.org/www-project-application-security-verification-standard/
- OWASP API Security Project: https://owasp.org/www-project-api-security/

Legal work should cover:
1. Terms of Service: account rules, acceptable use, AI output limitations, tool authorization, user content rights, third-party services, suspension/termination, complaint handling, and appropriate jurisdiction-specific liability/dispute clauses.
2. Privacy Policy: operator identity/contact, categories of data, purposes/legal bases, external AI/search/storage providers, retention, international transfers, user rights, cookies/sessions, security, deletion, complaints, and contact.
3. Data processing agreements with business customers or subprocessors where required.
4. Provider/subprocessor inventory and review of each provider's terms and data handling.
5. Consent UX for optional training or model improvement, separate from basic service operation.
6. Incident/breach response plan and recordkeeping.
7. Copyright and IP review for user uploads, generated content, and third-party integrations.
8. Consumer/payment terms, refunds/cancellation, tax obligations, and any sector-specific rules if commercial features are introduced.

Before launch, ask counsel to review the actual architecture and data-flow diagram, not just the draft text. Do not promise encryption, deletion, retention periods, or zero-training unless verified for the exact service and provider configuration.

## 8. Competitor landscape (initial desk research, not exhaustive)

This matrix compares adjacent categories and official product positioning. It is not a complete feature-by-feature benchmark; pricing/features change and must be rechecked before launch.

| Competitor/category | Publicly stated strength | Implication for Smart BethG | Potential differentiation to validate |
|---|---|---|---|
| ChatGPT / OpenAI | General assistant, business controls, data/privacy commitments, broad tool ecosystem | Users expect reliability, memory controls, privacy explanations, and polished onboarding | Transparent approval-to-execution audit trail, portable provider-neutral workflows, user-controlled project/task records |
| Claude / Anthropic | Strong writing/reasoning and coding workflows; commercial API privacy/retention documentation | Users compare reasoning quality, coding reliability, and data handling | Cross-provider orchestration without exposing model complexity; explainable action permissions |
| GitHub Copilot | Coding assistance, repository/IDE workflows, agents and code review | Developers expect integrations that fit existing engineering workflows | Broader project/work-agent workflow beyond code completion; explicit bounded actions and audit |
| Replit Agent | Prompt-to-app building, integrated development/deployment, self-testing features | App generation is a competitive market; “AI builds apps” alone is not defensible | Reliable persistent workspace, cross-project memory, approval/audit and deployment-provider portability |
| Zapier AI/Agents | Automation across many external apps, task-based usage and connector breadth | Integrations and predictable usage economics are major expectations | More developer-controlled, project-centric agent with inspectable execution; only if integrations are implemented and reliable |

Official competitor starting points:
- OpenAI security and privacy: https://openai.com/security-and-privacy/
- OpenAI business data: https://openai.com/business-data/
- GitHub Copilot plans: https://github.com/features/copilot/plans
- Replit Agent: https://replit.com/products/agent
- Replit pricing: https://replit.com/pricing
- Zapier pricing and Agents: https://zapier.com/pricing
- Anthropic commercial data retention information: https://privacy.claude.com/en/articles/7996866-how-long-do-you-store-my-organization-s-data

Do not claim Smart BethG is more private, cheaper, safer, or more capable than competitors until tested against comparable workloads and documented evidence. A multi-provider interface by itself is easy to copy. Durable execution, useful integrations, user trust, clear cost controls, and a focused customer problem are more credible candidates for differentiation.

## 9. Financial model and pricing method

Do not set permanent pricing by copying a competitor's monthly subscription. First measure:
- model/search calls per successful task;
- input/output tokens and provider cost;
- retry and failure cost;
- average and p95 task duration;
- storage and egress per active user;
- database, worker, monitoring, email, payment, and support cost;
- free-user conversion and abuse rates.

Start with a controlled private beta and a clear free quota. Enforce per-user budgets and a global spend ceiling. Consider a combination of subscription tiers, usage limits, and bring-your-own-provider-key only if the experience remains safe and supportable. Do not advertise “unlimited AI” when third-party provider costs are variable.

Suggested metrics:
- activation: percentage completing one successful useful task;
- task success: completed tasks / attempted tasks, split by feature;
- reliability: failure rate, queue wait, provider error rate, recovery success;
- retention: weekly active users and retained cohorts;
- cost: gross cost per active user and cost per successful task;
- economics: conversion, revenue per paying user, gross margin, refunds, churn;
- trust: approval rejection rate, security incidents, deletion/export completion time, support complaints.

## 10. Research and validation plan

### Week 1: establish evidence
- Confirm current main commit and workflow statuses.
- Build a route/API inventory and data-flow map.
- Produce an existing-feature matrix: implemented, partially implemented, schema-only, broken, untested.
- Interview 10–15 potential users; record tasks and current alternatives.
- Inventory all external providers and data sent to each.

### Week 2: risk and architecture
- Complete threat model and OWASP ASVS/API Security mapping.
- Add missing cross-user authorization tests.
- Verify PostgreSQL migrations and broaden repository integration tests.
- Test backup/restore and deployment from a clean environment.
- Specify durable jobs and object-storage interface before implementing multi-instance deployment.

### Weeks 3–4: vertical slices
- Finish projects/workspaces and file/artifact lifecycle.
- Finish mission/job lifecycle with durable status, cancellation, retries, and audit.
- Implement workflow definition validation and execution separately.
- Add privacy/account controls and user-facing approval history.
- Run end-to-end and accessibility tests on each slice.

### Weeks 5–6: private beta readiness
- Independent security review and remediation.
- Load/concurrency tests and provider-failure simulations.
- Finalize operational alerts, incident and recovery runbooks.
- Have counsel/DPCO review legal applicability and policy drafts.
- Run a small invited pilot with clear limits and consent, then measure success and cost.

These are planning windows, not guaranteed completion dates. Scope and timing must be revised when the repository audit reveals dependencies or defects.

## 11. Go/no-go decision

**No-go for unrestricted public registration until all critical gates are closed.** A limited, invited beta may be considered only after the core security boundary, data isolation, recovery, privacy disclosures, and operational controls have been verified and the operator has a way to respond to incidents.

A green CI run is necessary but insufficient. A production decision requires evidence from code review, automated tests, manual end-to-end testing, deployment and restore drills, independent security review, legal/privacy review, and actual user testing.

## 12. Living document maintenance

- Every audit, decision, migration, test baseline, and release gate must carry a date and commit reference.
- Add new dated findings rather than silently rewriting historical conclusions.
- For each finding record: ID, severity, affected component, evidence, impact, fix, test, owner, status, and verification commit.
- Update this roadmap after every major review and before every release.
