"""
Smart BethG
FastAPI Application Entry Point
"""
import os
import time

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware

import config
from database import initialize_database
from logging_setup import setup_logging, get_logger
from error_handlers import register_error_handlers

from routes import (
    health, auth, auth_google, tasks, agents, approvals, audit, tools,
    providers, chat, files, memory, knowledge, projects, artifacts, missions, training_export, pages,
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

    app = FastAPI(
        title="Smart BethG",
        version="1.0.0",
        description="Smart BethG AI Agent Platform API",
    )
    register_error_handlers(app)

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
    ]
    for router in api_routers:
        if router is chat.router or router is files.router:
            # Preserve legacy /api/chat and /api/files endpoints while exposing
            # canonical /api/v1/chat and /api/v1/files paths without double /api.
            app.include_router(router, prefix="/api")
            app.include_router(router, prefix=config.API_PREFIX)
        else:
            app.include_router(router)
            app.include_router(router, prefix=config.API_PREFIX)


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
