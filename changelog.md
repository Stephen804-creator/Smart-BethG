# Smart BethG — Changelog

Records what actually changed in the software. Compare against
`v1_capabilities.md` for current capability status; do not infer status
from this list alone.

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
