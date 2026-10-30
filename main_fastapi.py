"""
Smart BethG
FastAPI Application Entry Point
"""
import hmac
import os
import time
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware

import config
from database import initialize_database
from logging_setup import setup_logging, get_logger
from error_handlers import register_error_handlers
from middleware.upload_limits import UploadBodyLimitMiddleware

from routes import (
    health, auth, auth_google, tasks, agents, approvals, audit, tools,
    providers, chat, files, memory, knowledge, projects, artifacts, missions, workflows,
    social_content, social_publishing, research, evidence, connectors, jobs,
    training_export, pages, agent_intelligence, workspaces, sandbox, operations, units_21_24,
)
from services.operations_service import OperationsService

BASE_DIR = os.path.dirname(os.path.abspath(__file__))


def _build_url_for(app: FastAPI):
    """Adapt existing Jinja url_for calls to Starlette route naming."""
    def url_for(name: str, **kwargs):
        if name == "static":
            path = kwargs.pop("filename", None) or kwargs.pop("path", "")
            return app.url_path_for("static", path=path)
        return app.url_path_for(name, **kwargs)
    return url_for


def create_app() -> FastAPI:
    """Create and configure the Smart BethG FastAPI application."""
    setup_logging()
    app_logger = get_logger("app")

    config.ensure_storage_dirs()
    initialize_database()

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        app_logger.info(
            "Smart BethG starting up (env=%s, providers=%s)",
            config.ENVIRONMENT, config.DEFAULT_PROVIDER or "auto-detect",
        )
        try:
            yield
        finally:
            app_logger.info("Smart BethG shutting down")

    app = FastAPI(
        title="Smart BethG",
        version="1.0.0",
        description="Smart BethG AI Agent Platform API",
        lifespan=lifespan,
    )
    register_error_handlers(app)

    # Bound upload bodies before Starlette parses multipart forms and spools files.
    # The extra 1 MiB is reserved for multipart framing; the route independently
    # enforces the exact per-file byte limit.
    app.add_middleware(
        UploadBodyLimitMiddleware,
        max_body_bytes=config.MAX_UPLOAD_SIZE_BYTES + (1024 * 1024),
        max_concurrent=2,
        route_suffix=config.API_PREFIX + "/files",
    )

    @app.middleware("http")
    async def enforce_csrf_for_cookie_authenticated_mutations(request: Request, call_next):
        # Every unsafe browser request is protected, not just login/logout.
        # SessionMiddleware is outside this middleware, so request.session is
        # available. The token is not stored in a readable cookie; clients must
        # fetch /auth/csrf and send it in X-CSRF-Token.
        if request.method in {"POST", "PUT", "PATCH", "DELETE"}:
            expected = request.session.get("csrf_token")
            supplied = request.headers.get("X-CSRF-Token", "")
            if (
                not isinstance(expected, str)
                or not expected
                or not isinstance(supplied, str)
                or not supplied
                or not hmac.compare_digest(expected, supplied)
            ):
                from fastapi.responses import JSONResponse
                return JSONResponse(
                    {"detail": "CSRF validation failed. Fetch /auth/csrf and send X-CSRF-Token."},
                    status_code=403,
                    headers={"Cache-Control": "no-store"},
                )
        return await call_next(request)

    @app.middleware("http")
    async def security_headers(request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        response.headers["X-Permitted-Cross-Domain-Policies"] = "none"
        # Report-only rollout: first collect browser compatibility evidence
        # before enforcing CSP. Inline styles remain temporarily allowed
        # because templates still use style attributes; inline scripts and
        # eval remain disallowed by the proposed policy.
        response.headers["Content-Security-Policy-Report-Only"] = (
            "default-src 'self'; "
            "base-uri 'self'; "
            "object-src 'none'; "
            "frame-ancestors 'none'; "
            "form-action 'self'; "
            "script-src 'self'; "
            "style-src 'self' 'unsafe-inline' https://cdnjs.cloudflare.com; "
            "font-src 'self' data: https://cdnjs.cloudflare.com; "
            "img-src 'self' data: blob:; "
            "connect-src 'self'; "
            "upgrade-insecure-requests"
        )
        if config.IS_PRODUCTION and config.SESSION_HTTPS_ONLY:
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        return response

    operations_service = OperationsService()

    @app.middleware("http")
    async def log_requests(request: Request, call_next):
        start = time.monotonic()
        request_id = uuid.uuid4().hex
        request.state.request_id = request_id
        try:
            response = await call_next(request)
        except Exception:
            duration_ms = int((time.monotonic() - start) * 1000)
            app_logger.exception("Unhandled request error request_id=%s method=%s", request_id, request.method)
            operations_service.record_request(request_id, request.method, "/unmatched", 500, duration_ms)
            raise
        duration_ms = int((time.monotonic() - start) * 1000)
        route_obj = request.scope.get("route")
        route_template = getattr(route_obj, "path", "/unmatched")
        if not isinstance(route_template, str) or not route_template.startswith("/"):
            route_template = "/unmatched"
        operations_service.record_request(
            request_id, request.method, route_template, response.status_code, duration_ms
        )
        response.headers["X-Request-ID"] = request_id
        app_logger.info(
            "request_id=%s %s %s -> %s (%sms)",
            request_id, request.method, route_template, response.status_code, duration_ms,
        )
        return response

    # CORS is wired to exact configured origins. An empty allowlist allows
    # no cross-origin browser origins.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=config.ALLOWED_ORIGINS,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Content-Type", "Authorization", "X-CSRF-Token"],
    )

    app.add_middleware(
        SessionMiddleware,
        secret_key=config.SECRET_KEY,
        session_cookie=config.SESSION_COOKIE_NAME,
        https_only=config.SESSION_HTTPS_ONLY,
        same_site="lax",
        max_age=config.SESSION_MAX_AGE_SECONDS,
    )

    app.mount(
        "/static",
        StaticFiles(directory=os.path.join(BASE_DIR, "static")),
        name="static",
    )
    templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "templates"))
    templates.env.globals["url_for"] = _build_url_for(app)
    app.state.templates = templates

    app.include_router(pages.router)
    # OAuth callback URLs must match the provider console exactly.
    app.include_router(auth_google.router)
    # Admin-only internal endpoint; deliberately not dual-mounted.
    app.include_router(training_export.router)

    api_routers = [
        health.router, auth.router, tasks.router, agents.router, approvals.router,
        audit.router, tools.router, providers.router, chat.router, files.router,
        memory.router, knowledge.router, projects.router, artifacts.router, missions.router,
        workflows.router, social_content.router, social_publishing.router, research.router,
        evidence.router, connectors.router, jobs.router, agent_intelligence.router,
        workspaces.router, sandbox.router, operations.router, units_21_24.router,
    ]
    for router in api_routers:
        if router in (chat.router, files.router, memory.router, knowledge.router):
            # Preserve legacy /api/{chat,files,memory,knowledge} endpoints while
            # exposing canonical /api/v1/{chat,files,memory,knowledge} paths.
            app.include_router(router, prefix="/api")
            app.include_router(router, prefix=config.API_PREFIX)
        else:
            app.include_router(router)
            app.include_router(router, prefix=config.API_PREFIX)


    return app


app = create_app()
