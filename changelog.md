# Smart BethG — Changelog

Records what actually changed in the software. Compare against
`v1_capabilities.md` for current capability status; do not infer status
from this list alone.

## 2026-10-24 — UI/UX recovery and popover refinement

### Changed
- Added retry controls for failed conversation history and provider catalog requests.
- Restored the user's prompt to the composer after failed sends, reducing lost work.
- Prevented switching conversations or starting a new chat while a response is in progress.
- Added active conversation semantics and visible disabled-state styling.
- Moved account and usage popover presentation from inline JavaScript styles into shared responsive CSS.
- Removed the obsolete notifications-panel handler because the corresponding control is not part of the UI.

### Verification
- JavaScript syntax checks passed for `chat.js`, `app.js`, `topbar.js`, `login.js`, and `workspace-dashboard.js`.
- Shared CSS brace balance is valid; the reviewed chat/dashboard/login templates have no duplicate static IDs, aside from a repeated Jinja template ID expression used for rendered mission items.
- Browser/device testing is still outstanding. GitHub Actions remains failing on this branch, and the available connector did not return job details.

## 2026-10-24 — UI/UX standardization (branch: uiux/standardize-design-system)

### Changed
- Removed non-functional dashboard global search and the unsupported notification control instead of leaving misleading actions visible.
- Renamed the topbar account control to match its actual account-summary behavior.
- Removed duplicate chat heading and upgraded the composer to multiline input with Enter/Shift+Enter guidance.
- Added responsive composer refinements, active conversation styling, and shared CSS classes for chat history and approval cards.
- Added accessible status messages when conversation history or provider choices fail to load.
- Added `docs/UI_UX_AUDIT_2026-10-24.md`, covering all 17 UI/UX units and production follow-up work.

### Verification / not done
- Static source review only; browser/device and screen-reader journeys still require execution.
- GitHub Actions test workflow is failing on the branch; job details were not returned by the available API response. Do not merge until the failure is investigated and CI passes.
- Work remains in the UI/UX branch and has not been merged to `main`.

## 2026-09-19

### Fixed
- Frontend was completely disconnected from the backend: no `StaticFiles`
  mount, no `Jinja2Templates`, no `"/"` route existed anywhere in
  `main_fastapi.py`. `templates/` and `CSS/` were dead files. Fixed by
  mounting `/static`, wiring `Jinja2Templates`, and adding real page
  routes (`routes/pages.py`).
- Templates were written for Flask (`url_for('static', filename=...)`,
  dotted blueprint route names like `main.home`) but the app is FastAPI.
  Added a compatibility shim (`_build_url_for` in `main_fastapi.py`) and
  registered FastAPI routes under matching names, rather than rewriting
  the templates.
- **Security:** every protected route trusted a client-supplied
  `X-User-Id` header with no verification - any caller could impersonate
  any user. Replaced with signed, server-side sessions
  (`starlette.middleware.sessions.SessionMiddleware`, `SECRET_KEY` from
  `config.py`). `api/dependencies.get_current_user` now reads
  `request.session`, not a header.
- Removed a dead duplicate `auth.py` at the project root that duplicated
  `routes/auth.py` but was never imported.
- `login.html` was a static "Authentication module coming soon" page.
  Replaced with a working login/register form wired to the real
  `/auth/login` and `/auth/register` endpoints.

### Added
- `config.py`: single source of environment-driven configuration
  (storage root, database path resolution, secret key, provider keys,
  CORS origins). No deployment location or credential is hardcoded
  anywhere in the codebase.
- Real chat capability: `services/chat_service.py`,
  `repositories/conversation_repository.py`, `routes/chat.py`
  (`POST /api/chat`, `GET /api/chat/{id}`), `conversations` and
  `messages` tables, and `static/js/chat.js` wiring the existing
  `chat.html` markup to it. When no AI provider is configured, it
  returns an honest "not connected" message instead of a fabricated
  reply.
- `providers/anthropic_provider.py`: real implementation using the
  `anthropic` SDK (previously `raise NotImplementedError(...)`, same as
  every other provider). Used only when `ANTHROPIC_API_KEY` is set.
- `POST /auth/register`: intentionally open self-registration for this
  pre-launch testing phase (documented in the route's docstring as
  needing to be locked down before a public domain goes live).
- Database: added `missions`, `mission_runs`, `files`, `memory`,
  `research`, `evidence`, `workflows`, `artifacts`, `social_content`,
  `projects`, `logs` tables per `v1_capabilities.md`. Storage schema
  only - no functional logic reads/writes most of these yet (see status
  appendix in `v1_capabilities.md`).
- Canonical docs added to the repo: `idea.md`, `roadmap.md`,
  `v1_capabilities.md`, `changelog.md` (this file).

### Changed
- Home page (`index.html`) and chat page (`chat.html`) navigation no
  longer link to Study/Developer/Social/Automation - those templates are
  empty (0 bytes) with no capability behind them, and the product's own
  UI rule says not to expose a category before it's real.
- Home page now renders with real, computed data (system status is
  checked live: DB reachable, AI provider configured or not) instead of
  hardcoded or fabricated dashboard content.

### Known issues / explicitly not done this pass
- Registration is open with no rate limiting - fine for solo pre-domain
  testing, not acceptable before a public launch.
- Only one AI provider (Anthropic) is wired; OpenAI/Google/local remain
  stubs.
- Task queue (`POST /tasks`) still does not execute anything
  automatically.
- Memory, research, artifacts, workflows, files, social content: storage
  only, no functional logic yet.

## 2026-09-19 (session 2)

### Added
- **Real OpenAI and Google providers** (`providers/openai_provider.py`,
  `providers/google_provider.py`) - previously both `raise
  NotImplementedError(...)`. Registered automatically in
  `provider_manager.py` when `OPENAI_API_KEY` / `GOOGLE_API_KEY` (or
  `GEMINI_API_KEY`) are set. Users can now pick a provider per-message
  from a dropdown in the chat UI (`GET /api/chat/providers`); an
  unavailable/invalid choice falls back to the configured default
  instead of erroring.
- **Rate limiting** (`services/rate_limiter.py`): in-memory, per-IP,
  applied to `/auth/login` and `/auth/register`. Explicitly documented
  as per-process only - will not coordinate across multiple instances.
- **Registration gating**: `SMART_BETHG_REGISTRATION_OPEN` (default
  true) and `SMART_BETHG_INVITE_CODE` env vars let an operator close or
  gate self-registration before a public launch, without touching code.
- **PWA support**: `static/manifest.json`, `static/service-worker.js`
  (served at `/service-worker.js` for root scope), generated icons
  (`static/icons/`). The service worker only caches the static shell
  (pages, CSS, JS, icons) - it deliberately never intercepts `/api/*` or
  `/auth/*`, so it cannot serve a stale or fabricated chat reply while
  offline.

### Known issues / explicitly not done this pass
- Rate limiter and registration gate are still not "production-grade"
  auth hardening (no CAPTCHA, no email verification, no password reset).
- PWA is installable and has an app shell, but chat still requires a
  live connection - there is no offline chat, by design (see above).
- I still have not run this against a live server myself (no network in
  my working environment) - this needs to be run by you before you
  trust it.

## 2026-09-19 (session 3 — live deploy fix)

Found from the actual Render deploy log (first real live test).

### Fixed
- **Crash on every page** (`/`, `/chat`, `/login` all returned 500
  Internal Server Error): `TemplateResponse()` was called the old way
  (`TemplateResponse(name, {"request": request, ...})`). The Starlette
  version this project's `requirements.txt` resolves to on a fresh
  install now requires `request` as an explicit positional argument:
  `TemplateResponse(request, name, context)`. All three page routes now
  go through one `_render()` helper so this can't drift out of sync
  again in only one of the three places.
- Removed the now-unused duplicate `CSS/main.css` (byte-identical to
  `static/css/main.css`, which is the one actually served). Confirmed
  nothing else in the codebase referenced the old `CSS/` path before
  deleting it.
- Added a `/favicon.ico` route (serves the generated app icon) to stop
  the harmless but noisy 404 the browser's automatic favicon request
  was producing in the logs.

### Verified
- Could not reproduce the exact Starlette version locally (no network
  access in my working environment to `pip install`), so this fix is
  based on reading the traceback precisely, not re-running it myself.
  **This needs a real redeploy to confirm.**

## 2026-09-19 (session 4 — multi-model + login fix)

### Fixed
- Gemini default model (`gemini-2.0-flash`) had been retired by Google -
  exactly the 404 you saw. Root cause of the broader problem: model
  names were hardcoded and go stale every few months as providers
  retire/rename models.

### Added
- **Real multi-model support** (`providers/model_catalog.py`): a curated,
  dated list of currently-available models per provider (verified against
  each provider's own docs, not guessed) - Claude Haiku 4.5/Sonnet
  5/Opus 5, GPT-5.6 Luna/Terra and GPT-6 Astra, Gemini 3.5 Flash-Lite/3.6
  Flash/3.1 Pro. This file will go stale again eventually - it needs a
  periodic recheck, the same way this bug happened in the first place.
- **Auto mode** (default): Smart BethG picks a model tier (fast/balanced/
  capable) using a simple, explicitly-documented heuristic - message
  length, presence of code fences, and a short list of complexity
  keywords (refactor, debug, analyze, step-by-step, etc.). This is
  honestly labeled as Smart BethG's own simple heuristic, not a learned
  or provider-side router.
- Chat UI now has a grouped Auto / Provider / Model dropdown instead of
  a flat provider list. Selecting a specific model always overrides
  Auto for that message.
- Password show/hide toggle on the login/register form.

### Known issues / explicitly not done this pass
- The complexity heuristic is simple by design - it will sometimes pick
  a "fast" tier for a short-but-genuinely-hard question, and vice versa.
- Google OAuth sign-up was requested but not started - needs the
  operator to create OAuth credentials in Google Cloud Console first
  (see conversation).

## 2026-09-19 (session 5 — Google Sign-In, real usage tracking, home cleanup)

### Added
- **Google Sign-In** (`routes/auth_google.py`, Authlib): honestly hidden
  on the login page until `GOOGLE_OAUTH_CLIENT_ID` and
  `GOOGLE_OAUTH_CLIENT_SECRET` are set. Matches an existing
  password-based account by email if one exists (and links it), else
  creates a new account. `users` table gained `oauth_provider` /
  `oauth_subject` columns and `password_hash` is now nullable at the
  schema level for OAuth-only accounts (OAuth accounts still get a real,
  never-used random hash so old databases created before this change
  still work without a destructive migration).
- **Real token usage tracking**: every provider now returns actual
  input/output token counts straight from that provider's own API
  response (`response.usage` for Anthropic/OpenAI, `usage_metadata` for
  Google) - not estimated. Stored per-message
  (`messages.tokens_in`/`tokens_out`), aggregated per user via
  `GET /api/chat/usage`, shown in a real panel behind a new topbar icon.
- **Topbar standardized** across the home page and chat page: the same
  four icons (Notifications, Usage, Settings, Log out) now appear in
  both places, each backed by a real endpoint - the Notifications panel
  is honestly empty ("No notifications yet") since nothing generates a
  notification yet, rather than a decorative badge.

### Changed
- **Home page decluttered**: removed the "Notifications" and "Recent
  Activity" sections that always rendered in full (with headers) even
  though nothing ever populated them - exactly the kind of
  looks-functional-but-isn't clutter flagged. They're now a topbar icon
  instead. Removed the duplicate "Ask Smart BethG" quick-chat form at
  the bottom of the home page - there is now exactly one chat surface
  (`/chat`), and the home page just links to it clearly, instead of
  presenting two different half-chat experiences.
- Removed the now-dead `POST /chat` quick-submit route in
  `routes/pages.py` since nothing calls it anymore after the above.

### Known issues / explicitly not done this pass
- Notifications panel has no way to ever populate yet - there is no
  event in the system that generates a notification. It is honestly
  empty rather than showing fake activity.
- Google OAuth is implemented but **untested against real Google
  credentials** - I don't have network access to test the actual OAuth
  handshake myself. Needs a real end-to-end test once you add your
  client ID/secret.

## 2026-09-19 (session 6 — testing, logging, error handling, API versioning, real health checks)

Implements items 1-5 of the "next 15" list, in order.

### Added
- **Testing foundation** (T0105): `tests/` with 42 real unit tests
  covering auth, chat service, database schema/migrations, the model
  catalog, the Auto-mode complexity heuristic, provider manager
  fallback behaviour, rate limiting, and health checks. Uses the
  standard library's `unittest` (not pytest) specifically so it runs
  with zero extra dependencies: `python -m unittest discover -s tests
  -p "test_*.py"`. I ran this suite myself before packaging - all 42
  pass. `requirements-dev.txt` added for pytest as an optional
  alternative runner.
- **Logging** (T0103, `logging_setup.py`): structured logging to stdout
  (what Render's log viewer actually shows) plus best-effort rotating
  file logs under persistent storage. Named loggers for app/auth/chat/
  error. Login, logout, registration, and every chat request/reply
  (including which provider/model and token counts) now actually log
  something.
- **Centralized error handling** (T0104, `error_handlers.py`): every
  error response - HTTP exceptions, validation errors, and genuinely
  unexpected exceptions - now comes back as a consistent
  `{"error": {"message", "type", "status_code"}}` shape. Full tracebacks
  go to the log, never to the client. This is the fix that would have
  turned the earlier TemplateResponse crash into a clean JSON error
  instead of a bare "Internal Server Error" page.
- **Request logging middleware**: every request now logs
  `METHOD /path -> status (duration)` - the single log line that would
  have shown "GET /login -> 500" immediately during that earlier bug.
- **API versioning** (T0203): `/api/v1` is now the canonical prefix.
  Existing unversioned paths (`/auth/login`, `/tasks`, `/api/chat`, etc.)
  keep working unchanged - both point at the same handlers, so nothing
  the deployed frontend already calls broke. Google OAuth routes are
  intentionally NOT duplicated under `/api/v1` (Google Cloud Console is
  configured with one exact callback URL).
- **Real health checks** (T0204, `services/health_service.py`):
  `/health` now actually queries the database and actually inspects
  which AI providers are configured, instead of returning a static
  "ok". Background task execution is honestly reported as
  `not_implemented` (see known issues from session 1) rather than
  omitted or faked as healthy.
- Startup/shutdown log lines in `main_fastapi.py`.

### Known issues / explicitly not done this pass
- `chat.router`'s versioned mirror lands at `/api/v1/api/chat/...`
  (its own internal prefix already contains "api"). Cosmetic, not
  broken - documented in `main_fastapi.py` rather than silently
  special-cased.
- I still cannot run the actual FastAPI app in my environment (no
  network to install fastapi/starlette/httpx) - the 42 tests exercise
  the service/logic layer directly and all pass, but the FastAPI-level
  wiring (middleware order, exception handler registration, dual
  router mounting) is verified by careful reading, not by an actual
  request/response cycle. **Needs a real redeploy to confirm**, same
  caveat as every session before this one.
- Items 6-15 of the "next 15" list (authorization/roles, the approval
  workflow, and the actual agent architecture - request model, intent
  detection, planning, tool registry/execution, execution loop, result
  verifier, provider fallback) are unstarted. That's a genuinely large
  build - real agent architecture, not incremental fixes - and doing it
  properly needs its own focused session(s) rather than being rushed
  in behind this one.

## 2026-09-19 (session 7 — authorization, real tool execution, the actual agent loop, provider fallback)

Completes items 6-15 of the "next 15" list. All 90 tests pass
(`python -m unittest discover -s tests -p "test_*.py"`).

### Fixed
- **Real, live bug**: `ApprovalService` stored approvals in a plain
  Python dict, and `api/dependencies.get_approval_service()` created a
  brand new instance on every request - so an approval created on one
  request was already gone before any later request could read or
  decide it. Approvals could never actually work. Now persists to the
  `approvals` table (which existed but nothing wrote to it). Removed a
  second, redundant, entirely-unused in-memory `ApprovalManager` found
  in `security/`.
- **Real correctness bug in `GitTool`**: `status()` returned only
  stdout, discarding the exit code and stderr - so a failed git command
  (e.g. run outside a repository) looked identical to a successful one
  to any caller. Fixed to return the full result so it can actually be
  verified.
- Removed dead `models/*.py` stub files (`class Task: pass` etc.,
  literally empty, never imported anywhere) and stray committed
  `__pycache__` directories.

### Added
- **Authorization (T0303)**: `users.role` (`user`/`admin`),
  `security/role_permissions.py` maps roles to real tool permissions,
  `require_role()` dependency. Role is now part of every user dict
  returned by auth.
- **Real tool execution (T0601/T0602)**: discovered the project already
  had a complete, well-designed security stack (`PolicyEngine`,
  `RiskEngine`, `AccessControl`, `SandboxManager`, `ExecutionEngine`)
  and real tool implementations (`FileReader`, `FileWriter`, `GitTool`,
  `CommandRunner`) - all fully built but never connected to anything.
  `services/tool_service.py` wires them together for real:
  `filesystem.read`, `filesystem.write`, `git.read`, `terminal.execute`
  now actually run, through the real permission → risk → approval →
  execution → verification pipeline. Verified against real files and
  real git, not mocks.
- **Result verifier (T0405, `agent/result_verifier.py`)**: catches the
  "tool didn't raise but also didn't succeed" case - e.g. a non-zero
  exit code is never reported as success just because nothing raised.
- **Agent request model, intent detection, planner (T0401-T0403,
  `agent/` package)**: intent detection deliberately only recognizes
  `git.read` (needs no argument extraction from free text) and falls
  back to chat for everything else - explicitly not attempting
  unreliable NLU for file paths or shell commands when the other end
  actually executes something.
- **The actual execution loop (T0404, `agent/executor.py`)**: wired into
  `Controller.handle_request()`, which previously only ever inserted a
  `"queued"` task row that nothing ever read again - the single most
  repeated gap flagged since the first review of this project. A
  request now actually gets classified, planned, and either answered via
  chat or executed as a real tool call, and the task row's status is
  updated to reflect what actually happened.
- **Provider fallback (T0503)**: if the selected/auto-chosen provider's
  API call fails, chat now tries every other currently-configured
  provider (priority order) before giving up, and only returns the
  honest failure message if all of them fail. The response records
  which provider actually answered and whether a fallback happened.

### Known issues / explicitly not done this pass
- Multi-step planning is still not implemented (see `agent/planner.py`
  docstring) - every plan is exactly one step.
- Intent detection only recognizes one tool trigger (`git.read`).
  `filesystem.read`/`filesystem.write`/`terminal.execute` are real and
  wired, but nothing currently routes a natural-language request to
  them - they're reachable today only via a direct tool call, not
  through chat text.
- The UI doesn't yet surface `fallback_used` or the approval-required
  state from a chat message - the API returns them, the frontend
  doesn't render them yet.
- Same standing caveat as every session: I still cannot run the actual
  FastAPI server in my environment. All 90 tests exercise the service/
  logic layer directly (including real file I/O and real git
  subprocess calls) and all pass, but the live HTTP request path is
  still unverified by me. **Needs a real redeploy to confirm.**

## 2026-09-19 (session 8 — model evaluation, full tool lifecycle, chat unified with the agent loop, real audit trail)

114 tests pass (`python -m unittest discover -s tests -p "test_*.py"`).
Completes items 1-5 of the second "next 15" list.

### Added
- **Model evaluation (T0504)**: `provider_calls` table + `ModelEvaluationService`
  records every provider call attempt - including ones that failed and
  got silently retried via fallback, not just the eventual successful
  one. `GET /api/chat/model-stats` exposes real success-rate/latency per
  provider+model.
- **Full tool lifecycle (T0603/T0604)**: the 3 remaining registered-but-
  unwired tools now actually work: `git.write` (narrow - `git add -A` +
  `git commit -m`, not an arbitrary git passthrough, since it's a
  HIGH-risk action requiring approval), `network.request`, `docker.run`.
  All 7 tools in `controller.ToolOrchestrator` are now real.
- **Chat unified with the agent loop**: `POST /api/chat` - the endpoint
  the actual chat UI calls - previously called `ChatService` directly
  and never reached intent detection or tool execution at all. Only the
  separate, UI-less `/tasks` endpoint did. Typing "check my repo status"
  into chat could only ever be answered by the AI provider making
  something up, never by actually checking. Now it routes through
  `agent/executor.py`, so a recognized intent (currently just
  `git.read`) genuinely executes. Tool-triggered exchanges are now
  recorded in conversation history the same way normal replies are.
- **Real audit trail**: nothing ever wrote to the `audit_events` table
  before this - `GET /audit` could only ever return an empty list no
  matter what happened, despite the table and route existing. Every
  tool authorization decision (deny / approval_required / executed) is
  now recorded. Added `GET /audit/all` (admin-only, using the
  `require_role("admin")` dependency built in the previous session but
  never applied to a real endpoint until now).
- Chat UI now surfaces state that used to be silently dropped: a small
  note under a reply when a fallback provider was used, or when the
  reply came from a tool action rather than the AI model.

### Fixed
- `chat.js`/`agent/request.py`: provider/model `selection` is now
  correctly threaded through the agent loop - it was at risk of being
  silently dropped once chat started routing through the executor
  instead of calling `ChatService` directly.

### Known issues / explicitly not done this pass
- Remaining items from the second "next 15": file manager/search/
  understanding, the full memory system (6 sub-tasks), and broadening
  intent detection to `filesystem.read` are not started - each is
  comparably sized to what's in this session, so continuing straight
  into all of them here risked the same kind of rushed mistake as the
  `provider_manager.py` edit two sessions ago. Stopping at a verified
  checkpoint instead.
- Same standing caveat: still cannot run the actual FastAPI server in
  my environment. All 114 tests exercise the service/logic layer
  directly (including real file I/O, real git and subprocess calls,
  and a confirmed-missing docker binary) and all pass, but the live
  HTTP request path remains unverified by me.

## 2026-09-19 (session 9 — file system, full memory system, filesystem.read intent)

158 tests pass (`python -m unittest discover -s tests -p "test_*.py"`).
Completes items 6-15 of the second "next 15" list - the full second
batch is now done.

### Added
- **File manager (T0701)**: real upload/list/download/delete against
  the `files` table (schema-only until now). Filenames sanitized,
  storage confined to a per-user directory under the app's own storage
  root, upload size capped (`SMART_BETHG_MAX_UPLOAD_BYTES`).
- **File search (T0702)**: filename search always; content search
  additionally for recognized plain-text file types - reads matching
  files at search time rather than maintaining a fake/stale index.
- **File understanding (T0703)**: real text extraction (plain text
  files read directly; PDFs via `pypdf`, newly added to
  `requirements.txt` rather than assumed present) and real AI
  summarization - honestly reports either step failing instead of
  fabricating a summary. Tested against a real PDF generated with the
  actual `pypdf` library, not a mock.
- **Memory system (T0801-T0806)**: three scopes - conversation,
  user, project (working/session memory from the original phase list
  are deliberately collapsed into one "conversation" scope; the system
  has no multi-step reasoning loop yet, so building two mechanisms for
  a distinction that doesn't concretely exist would be premature).
  Retrieval is honest about what it is - everything in the relevant
  scopes, not embedding/relevance-ranked search, and documented as not
  scaling to hundreds of entries. Governance is real:
  `GET/POST/DELETE /api/memory` lets a user see and delete everything
  remembered about them.
- **Memory is now wired into chat, not just stored**: `ChatService.send`
  recalls relevant memory and injects it before every provider call -
  tested end to end (a "remember that I prefer Python" followed by an
  unrelated question, confirming the fact actually reaches the
  simulated provider call).
- **`filesystem.read` is now reachable from chat text** - the last of
  the three tools intent detection was deliberately withholding.
  Extraction only trusts quoted/backticked paths or an unambiguous bare
  filename (word chars + real extension); anything else produces a
  "clarify" plan step that asks which file, rather than guessing at one
  and reading the wrong file.
- New "remember that ..." intent (`memory.write`) - narrow trigger,
  anchored so "do you remember what I said?" (a question) correctly
  falls through to chat instead of being misread as a write instruction.

### Known issues / explicitly not done this pass
- Memory retrieval has no relevance ranking or embedding search - it
  returns everything in scope, bounded by a fixed cap
  (`MAX_CONTEXT_MEMORIES`). Fine for a handful of memories per user,
  will need real semantic retrieval before it scales further.
- `terminal.execute` is still not reachable from chat text - a wrong
  guess at a shell command is a materially different risk than asking
  "which file?" again, so this is intentionally still not attempted.
- Same standing caveat: still cannot run the actual FastAPI server in
  my environment. All 158 tests exercise the service/logic layer
  directly (including real file uploads, real PDF parsing, real memory
  persistence and recall) and all pass, but the live HTTP request path
  remains unverified by me.

## 2026-09-19 (session 10 — real multi-step planning, web research)

174 tests pass (`python -m unittest discover -s tests -p "test_*.py"`).
Completes item 1 (multi-step planning, inserted as a prerequisite) and
items 6-9 (T1001-T1004, the Research phase) of the third "next 15" list.

### Added
- **Real multi-step planning**: `agent/executor.py`'s loop now runs
  every step in a plan, in order, carrying context from earlier steps
  into later ones - not just `plan.steps[0]`. Every existing single-step
  intent (git.read, memory.write, filesystem.read) is unaffected; this
  is additive, not a rewrite of what already worked.
- **Web research (T1001-T1004)**: real search via the Brave Search API
  (`services/search_service.py`, `BRAVE_SEARCH_API_KEY`) - not a scrape
  of a search results page, and not fabricated when unconfigured (raises
  a clear error instead of pretending to have searched). A "research X"
  request is now a genuine two-step plan: search, then a synthesis step
  that receives the actual search results as context and is explicitly
  instructed to cite the specific URLs behind each claim and to say so
  honestly if the results don't support a confident answer. If the
  search step itself fails or returns nothing, the plan stops there and
  reports that - it does not fall through to the AI making something up.
- New `research` intent, narrow and anchored the same way as
  `memory.write` - "research quantum computing" is an instruction;
  "I did some research on this yesterday" (not at the start) correctly
  falls through to chat.

### Known issues / explicitly not done this pass
- Research planning is single-query only - it does not decompose a
  broad topic into several different search queries. A genuinely harder
  research question gets one search, not an investigation.
- Verification is prompt-level ("cite your sources, say so if unsure"),
  not a separate fact-checking pass that cross-references claims against
  full source text.
- Local knowledge base / RAG over uploaded files (as opposed to live web
  search) is still not started - that's a separate capability from web
  research and is next.
- Code intelligence (T1101-T1105), git operations beyond status/commit
  (T1201+), and PWA-to-native app packaging are all still not started.
- Same standing, unchangeable-by-me caveat: I have no network access in
  my working environment, so I cannot run the actual FastAPI server or
  make a real call to Brave's API myself. All 174 tests exercise the
  service/logic layer directly, with the real HTTP call structure
  verified against Brave's documented response shape (mocked, not live).
  **This needs a real redeploy and a real search to confirm end to end.**

## 2026-09-19 (session 11 — knowledge base/RAG, code intelligence, native shell)

208 tests pass (`python -m unittest discover -s tests -p "test_*.py"`).
Completes the remainder of the third "next 15" list.

### Added
- **Knowledge base (T0901-T0904)**: `POST /api/files/{id}/ingest` chunks an
  uploaded file into a searchable knowledge base (`knowledge_chunks`
  table); `GET /api/knowledge/search` exposes the same retrieval chat
  uses. Retrieval is real semantic search (cosine similarity over
  embeddings) when an OpenAI or Google key is configured
  (`embed()` added to both providers; Anthropic has no embeddings API), and
  an honest keyword-overlap fallback when neither is - documented as NOT
  semantic in that case. Retrieved excerpts are injected into chat, guarded
  by a cheap "does this user have any knowledge?" check so no embedding API
  call is made for users who never ingested anything. Ingest is an explicit
  action, not automatic on upload - not every upload should become
  permanent context for every future chat.
- **Code intelligence (T1101, T1104, T1105)**: new `code.explain` and
  `code.review` intents ("explain the file X", "review the file X",
  "debug the file X"). Each is a genuine two-step plan: a real,
  permission-checked, workspace-confined `filesystem.read`, then a chat
  step that receives the file's actual contents plus a specific
  instruction (review prompt explicitly says to say so rather than invent
  a problem). If the read fails, is denied, or path-traversal is blocked,
  the plan stops - the AI is never asked to explain a file it wasn't
  actually given.
- Executor generalized so a `tool` step can be non-terminal (chained into a
  following chat step) - the same mechanism research already used.
- **Native shell (`native/`)**: Capacitor config that loads the *deployed*
  site in a webview. Smart BethG is server-rendered, so there are no static
  files to bundle; the URL comes from `SMART_BETHG_URL` (never hardcoded,
  must be https). Includes a README with honest limits.
- Tests guarding PWA assets: every manifest icon and every precached
  service-worker file must exist on disk (a single missing precache file
  makes the whole service-worker install fail silently).

### Fixed
- Keyword fallback compared raw tokens including trailing punctuation, so
  "refunds?" never matched "Refunds" - found by an end-to-end test, fixed in
  the code rather than the test.

### Known issues / explicitly not done
- **Code generation and code modification (T1102/T1103) have no dedicated
  intent, on purpose.** Generating code already works through plain chat.
  Saving or applying it would mean reliably extracting "which code block goes
  to which filename" from free text and then writing files - a wrong guess
  overwrites a real file. `filesystem.write` exists and is approval-gated for
  explicit, structured calls; auto-applying AI output from chat text is not
  something to fake.
- **The native shell has not been built or run by me** - it needs Android
  Studio / Xcode, which I don't have. Apple may reject a webview wrapper
  (guideline 4.2). The installable PWA is the zero-cost path and already works.
- Desktop packaging (Tauri/Electron) is not set up; installing the PWA from
  Chrome/Edge is the working desktop path today.
- Knowledge retrieval: no vector database - similarity is computed in Python
  over all of one user's chunks. Fine for personal file counts; would need
  replacing before scaling to shared/large corpora.
- Research remains single-query; verification remains prompt-level.
- Repository operations beyond status/commit (branches, diffs, PRs; T1201+)
  are not started.
- **Unchanged and not closable by me:** I have no network in my working
  environment, so I have never run the real FastAPI server, made a live
  Brave/OpenAI/Google call, or executed a real embedding request. 208 tests
  cover the logic layer thoroughly (real files, real git, real PDF parsing,
  mocked provider/HTTP responses); the live path needs your redeploy.

## 2026-10-02 (session 12 — free open-weight providers: Groq, OpenRouter)

222 tests pass. Adds two free, no-card-required AI providers.

### Added
- **Groq provider** (`providers/groq_provider.py`): hosts open-weight
  models (GPT-OSS, Qwen) on real GPUs, free, rate-limited not
  token-limited. `GROQ_API_KEY`. Verified current model IDs -
  `llama-3.3-70b-versatile` (the obvious guess) was retired by Groq on
  2026-08-16; the catalog uses its confirmed replacements
  (`openai/gpt-oss-20b`, `qwen/qwen3.6-27b`, `openai/gpt-oss-120b`)
  instead, and a test locks in that the retired ID never silently
  comes back.
- **OpenRouter provider** (`providers/openrouter_provider.py`):
  aggregates 190+ models including free ones. `OPENROUTER_API_KEY`.
  Uses `openrouter/free` - OpenRouter's own auto-router - as the
  default rather than a hardcoded `<model>:free` ID, because
  OpenRouter's free lineup changes on the order of weeks (their own
  public changelog shows entries added/removed days apart). A specific
  model can still be requested explicitly via the model picker.
- `OpenAIProvider` refactored to accept a configurable `API_BASE_URL`/
  `CATALOG_NAME`/`EXTRA_HEADERS`, since Groq and OpenRouter both speak
  the same OpenAI-compatible API shape - both new providers are thin
  subclasses, not new integrations written from scratch.
- Fallback order is now
  `anthropic > openai > google > groq > openrouter`: paid providers
  first when configured, free ones as a genuine safety net - and with
  zero special-casing, Groq/OpenRouter simply become the default when
  no paid key exists at all.
- Neither is used for embeddings (`embedding_provider_name()` still
  only checks openai/google) - neither Groq nor OpenRouter exposes an
  embeddings endpoint.

### Known issues
- OpenRouter's free-model churn means `openrouter/free` is the
  resilient choice, but it also means you don't get to pick exactly
  which model answers unless you name one explicitly - a real tradeoff
  of relying on a free, shifting resource rather than a paid, stable one.
- Same standing caveat: I have not made a real call to either API -
  registration/priority logic is tested with stubbed SDKs (`openai`/
  `anthropic` aren't installed in my sandbox), not a live request.

## 2026-10-03 (session 13 — admin-only training data exporter)

234 tests pass. Feeds the "BethG Core" fine-tuning path discussed with
the operator - exports real conversation data for offline fine-tuning
of an open-weight model, which later plugs back in as a provider
(same pattern as Groq/OpenRouter). Not wired to any live/automatic
retraining loop - intentionally a manual, operator-controlled step.

### Added
- **`GET /admin/training-export`** and **`/preview`**
  (`services/training_export_service.py`,
  `repositories/training_export_repository.py`): admin-only
  (`require_role("admin")`), not dual-mounted under `/api/v1` since this
  is an internal tool, not a public API surface. Exports real
  conversation exchanges in standard chat fine-tuning JSON shape
  (`{"messages": [...]}` per conversation).
- Two honesty filters, both tested: (1) only exchanges where the
  assistant reply came from a real, configured AI provider are
  included - the "isn't connected yet" / "could not reach any
  provider" failure messages and synthesized tool/memory exchanges
  (`provider = 'agent'`) are excluded, since they'd teach a model to
  fail or recite boilerplate rather than demonstrate real assistant
  behavior; (2) no username/user_id/account identifier is included in
  the export, only message content - a privacy-conscious default, not
  a substitute for telling users conversations may be used this way.
- `require_role()` - the dependency that's been gating the admin audit
  view since an earlier session - finally has direct test coverage of
  its own (admin passes, non-admin rejected, missing/unknown role both
  fail closed).

### Known issues / explicitly not done
- Pairing cleanup (dropping a trailing unanswered question) is
  best-effort, not guaranteed-correct - this export is a starting
  point for human review before fine-tuning, not a ready-to-train
  dataset, and is documented as such.
- No UI for this yet - admin must call the endpoint directly. Fits the
  "admin chamber" pattern discussed but the screen itself isn't built.
- Same standing, unchangeable-by-me caveat: untested against a live
  server; verified via 234 tests against the service/logic layer.


## 2026-10-10 UTC — Public-launch architecture and security audit

**Recorded in Git history:** the commit timestamp is the exact time for this entry. This entry supersedes earlier statements where current behavior differs.

### Architecture decisions activated
- PostgreSQL is now the required production database for both single-instance and multi-instance deployments. SQLite is retained for local development and isolated unit tests.
- Added a PostgreSQL DB-API compatibility adapter, a shared PostgreSQL-backed authentication rate limiter, a PostgreSQL CI service, and integration smoke tests.
- Added a fail-closed SQLite-to-PostgreSQL data migration utility and a dated migration runbook. The utility copies rows only; files and storage paths need a separate verified migration.
- Added provider-neutral setup/deployment documentation. No Render-specific manifest or provider runtime is required.
- Recorded the public-launch target and decisions for token budgets, shared storage, approvals, and schema-backed feature areas in `architecture.md` and `docs/DECISION_LOG.md`.

### Security and reliability changes
- Approval records now persist the operation payload, owner, resource/workspace, expiry, decision, execution state, and result. The approval service atomically claims approved operations and rejects duplicate execution; the tool service rechecks permissions and executes the saved operation once. Crash outcomes remain non-replayable and require reconciliation.
- The chat approval UI now shows the exact saved arguments and reports execution status.
- Tool workspaces are separated by authenticated user ID.
- Upload reads are bounded before the entire file is loaded into memory.
- Network requests reject non-HTTP schemes, embedded credentials, non-public IP destinations, and oversized responses; redirects are revalidated.
- Docker CLI passthrough is restricted to read-only inspection or explicitly allowlisted, constrained container runs.
- Unsandboxed host Python execution is disabled in production. A real isolated job runner is still required before public code execution.
- CORS allowlist is wired; registration defaults closed; OAuth creation respects registration state and requires a verified Google email; authentication input lengths are bounded.
- Dynamic account/usage data in the topbar is rendered with DOM text nodes rather than interpolated into HTML.
- Fixed the versioned chat route to `/api/v1/chat` while preserving the legacy `/api/chat` endpoint.
- Training export remains disabled until explicit, recorded, revocable user consent is implemented.

### Documentation added
- `README.md` — provider-neutral local/production setup.
- `docs/DECISION_LOG.md` — dated active decisions.
- `docs/TERMS_OF_SERVICE_DRAFT_2026-10-10.md` and `docs/PRIVACY_POLICY_DRAFT_2026-10-10.md` — drafts requiring legal and product review.
- `docs/REPOSITORY_AUDIT_2026-10-10.md` — living whole-repository findings and verification matrix.
- `docs/DATABASE_MIGRATION_2026-10-10.md` — migration and rollback checklist.
- `scripts/manage_user.py` — trusted CLI for initial administrator setup.

### Verification status and remaining work
- A PostgreSQL integration CI job passed an earlier revision for user creation, conversation persistence, approval persistence, and database-backed rate limiting. The latest revision must pass both CI jobs before merge.
- Do not treat this change log as proof of live deployment persistence, backups, legal approval, independent security review, or multi-instance file-storage readiness.
- Still open: complete owner-isolation audit, end-to-end approval and crash-recovery tests, versioned schema migrations, per-user/global token-spend enforcement, shared file/workspace storage, durable background jobs, real sandboxing, dependency/secret scanning, CSRF/session hardening, password reset/MFA/account deletion, browser accessibility testing, and feature vertical slices for projects/missions/workflows/artifacts/social content/research/evidence.
- Public launch remains **not approved** until the release gates in the dated audit report are verified.

## 2026-10-10 — Whole-codebase audit continuation

- Fixed a latent task ownership flaw: status updates now require the owning user ID and validate the allowed status values. Controller call sites now pass the authenticated owner; regression tests cover owner isolation and status validation.
- Removed a placeholder Subresource Integrity hash from the home-page Font Awesome stylesheet and added a regression test to prevent the placeholder from returning.
- Expanded PostgreSQL CI integration coverage to exercise the core capability services, including projects, missions, workflows, social-content drafts, research, evidence, memory, artifacts, and task status updates.
- Replaced a host-specific native-app URL example with a provider-neutral deployment URL. Updated README launch gates to reflect what is implemented versus what remains incomplete.
- Added dated architecture/decision records and draft Terms of Service and Privacy Policy documents. These are planning drafts and are not approved legal policies.
- Latest confirmed checks at this point: dependency audit and Gitleaks passed on the branch; PostgreSQL smoke tests passed on the preceding capability-test commit. The newest combined unit/PostgreSQL run is still being checked before merge.


## 2026-10-13 — PostgreSQL-only database correction

- Removed the application's SQLite connection and schema-initialization fallback; PostgreSQL is now required for local development, tests, and production.
- Kept SQLite only in the explicit legacy data migration utility, which reads the source database and does not delete or modify it.
- Added a local PostgreSQL 16 Docker Compose service and updated local-development instructions.
- Changed unit-test setup to use isolated PostgreSQL schemas and updated the CI unit-test job to provide PostgreSQL.
- Removed the SQLite-specific rate-limiter transaction branch; all environments use PostgreSQL advisory locking.
- **Verification pending:** tests and CI were not run as part of this code-correction pass. Do not treat the branch as validated until PostgreSQL CI and the legacy migration rehearsal pass.

## 2026-10-24 — Units 2–4 foundation follow-up

- Added a controlled local-to-shared storage migration utility for database-referenced uploads and artifacts. Dry-run is the default; apply verifies copied bytes and confirms the database row has not changed before switching its locator. Local source files are retained for rollback.
- Added conservative memory and knowledge disagreement signals for similar statements with polarity/numeric differences. These signals warn for review and never silently resolve a conflict.
- Added unit tests for conflict-signal behavior and updated the foundation backlog to distinguish completed foundations from deferred semantic memory retrieval, OCR, advanced reranking, external-source verification, and approval-based memory consolidation.
- Corrected the test workflow's unsupported runner context in job-level environment configuration so named CI jobs can start. Verification is still in progress; see PR #12 checks before merging.


## 2026-10-24 — Roadmap Units 6–9 implementation branch

- Added the typed capability registry prerequisite, connector catalog/installations, trusted adapter interface, and permission-aware action service.
- Added a fail-closed policy engine; write/destructive/financial actions require persisted approval and are revalidated before execution. Legacy host-side actions remain disabled.
- Added PostgreSQL-backed background jobs with idempotency, leases, priorities, bounded retries, guarded completion, owner-scoped status/cancel endpoints, and a separate worker entry point.
- Added validated connector-action plans to missions. Mission run creation and queue insertion share one transaction; the worker persists progress and pauses/resumes around approval-required steps.
- Live external OAuth/token lifecycle and GitHub/Drive/Slack adapters are not included yet; those catalog entries are intentionally non-executable until trusted adapters are implemented and connected.
