"""
Smart BethG
FastAPI Application Entry Point
"""
import os
import time

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware

import config
from database import initialize_database
from logging_setup import setup_logging, get_logger
from error_handlers import register_error_handlers

from routes import (
    health,
    auth,
    auth_google,
    tasks,
    agents,
    approvals,
    audit,
    tools,
    providers,
    chat,
    files,
    memory,
    knowledge,
    training_export,
    pages,
)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))


def _build_url_for(app: FastAPI):
    """
    Compatibility shim so the existing Jinja templates - written with
    Flask's url_for('static', filename=...) / url_for('blueprint.endpoint')
    conventions - work unmodified against FastAPI/Starlette's routing,
    which expects url_path_for(name, path=...) and undotted route names.
    Route names containing dots (e.g. "main.home") are just strings to
    Starlette, so registering routes with those exact names is enough.
    """

    def url_for(name: str, **kwargs):
        if name == "static":
            path = kwargs.pop("filename", None) or kwargs.pop("path", "")
            return app.url_path_for("static", path=path)
        return app.url_path_for(name, **kwargs)

    return url_for


def create_app() -> FastAPI:
    """
    Create and configure the Smart BethG FastAPI application.
    """

    setup_logging()
    app_logger = get_logger("app")

    config.ensure_storage_dirs()
    initialize_database()

    app = FastAPI(
        title="Smart BethG",
        version="1.0.0",
        description="Smart BethG AI Agent Platform API",
    )

    register_error_handlers(app)

    @app.middleware("http")
    async def log_requests(request: Request, call_next):
        """
        Logs every request's method/path/status/duration. This is the
        single place that would have shown "GET /login -> 500" instantly
        during the earlier live-deploy crash, instead of relying on the
        client screenshot.
        """
        start = time.monotonic()
        response = await call_next(request)
        duration_ms = (time.monotonic() - start) * 1000
        app_logger.info(
            "%s %s -> %s (%.1fms)",
            request.method, request.url.path, response.status_code, duration_ms,
        )
        return response

    # Sessions back real authentication (see api/dependencies.get_current_user).
    # SECRET_KEY is required to be set via env var in production - see config.py.
    app.add_middleware(
        SessionMiddleware,
        secret_key=config.SECRET_KEY,
        session_cookie=config.SESSION_COOKIE_NAME,
        https_only=config.SESSION_HTTPS_ONLY,
        same_site="lax",
    )

    # Static assets (CSS/JS) - previously unmounted, so the frontend could
    # never actually load anything.
    app.mount(
        "/static",
        StaticFiles(directory=os.path.join(BASE_DIR, "static")),
        name="static",
    )

    templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "templates"))
    templates.env.globals["url_for"] = _build_url_for(app)
    app.state.templates = templates

    # HTML pages
    app.include_router(pages.router)

    # Google OAuth is mounted only at its original path - never
    # versioned/duplicated. Google Cloud Console is configured with one
    # exact callback URL; mounting a second copy under /api/v1 would add
    # a redirect endpoint Google never calls and that request.url_for()
    # could ambiguously resolve to, for no benefit.
    app.include_router(auth_google.router)

    # Admin-only internal tool, not a public API surface - deliberately
    # not dual-mounted under /api/v1 the way the regular JSON API is.
    app.include_router(training_export.router)

    # JSON API - mounted at both its original path (kept working since
    # the deployed frontend already calls these) and under /api/v1 (the
    # new canonical, versioned location). Both point at the same router
    # instance/handlers, so there is no behavioural difference between
    # them - this is purely a routing addition, not a rewrite.
    api_routers = [
        health.router,
        auth.router,
        tasks.router,
        agents.router,
        approvals.router,
        audit.router,
        tools.router,
        providers.router,
        chat.router,
        files.router,
        memory.router,
        knowledge.router,
    ]
    for router in api_routers:
        app.include_router(router)
        app.include_router(router, prefix=config.API_PREFIX)
    # Known cosmetic wart: chat.router's own prefix is already "/api/chat"
    # (kept as-is for the deployed frontend), so its versioned mirror above
    # lands at "/api/v1/api/chat/..." - redundant but not broken. Cleaning
    # this up means changing chat.router's internal prefix to "/chat" and
    # updating every fetch() call in chat.js/topbar.js to match, which is
    # a real (small) task, not something to special-case here silently.

    @app.on_event("startup")
    async def on_startup():
        app_logger.info(
            "Smart BethG starting up (env=%s, providers=%s)",
            config.ENVIRONMENT, config.DEFAULT_PROVIDER or "auto-detect",
        )

    @app.on_event("shutdown")
    async def on_shutdown():
        app_logger.info("Smart BethG shutting down")

    return app


app = create_app()
