"""
Smart BethG
FastAPI Application Entry Point
"""
import hmac
import os
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware

import config
from database import initialize_database
from logging_setup import setup_logging, get_logger
from security.request_size_limit import RequestBodyLimitMiddleware
from error_handlers import register_error_handlers

from routes import (
    health, auth, auth_google, tasks, agents, approvals, audit, tools,
    providers, chat, files, memory, knowledge, projects, artifacts, missions, workflows, social_content, social_campaigns, connectors, research, evidence, training_export, pages,
)

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

    @app.middleware("http")
    async def log_requests(request: Request, call_next):
        start = time.monotonic()
        response = await call_next(request)
        duration_ms = (time.monotonic() - start) * 1000
        app_logger.info(
            "%s %s -> %s (%.1fms)",
            request.method, request.url.path, response.status_code, duration_ms,
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

    # This outer ASGI middleware limits both declared and streamed request
    # bodies before multipart parsing can consume unbounded disk/memory.
    app.add_middleware(
        RequestBodyLimitMiddleware,
        max_body_bytes=config.MAX_REQUEST_BODY_BYTES,
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
        memory.router, knowledge.router, projects.router, artifacts.router, missions.router, workflows.router, social_content.router, social_campaigns.router, connectors.router, research.router, evidence.router,
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
