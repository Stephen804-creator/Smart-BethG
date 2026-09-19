"""
Smart BethG
FastAPI Application Entry Point
"""
import os

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware

import config
from database import initialize_database

from routes import (
    health,
    auth,
    tasks,
    agents,
    approvals,
    audit,
    tools,
    providers,
    chat,
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

    config.ensure_storage_dirs()
    initialize_database()

    app = FastAPI(
        title="Smart BethG",
        version="1.0.0",
        description="Smart BethG AI Agent Platform API",
    )

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

    # JSON API
    app.include_router(health.router)
    app.include_router(auth.router)
    app.include_router(tasks.router)
    app.include_router(agents.router)
    app.include_router(approvals.router)
    app.include_router(audit.router)
    app.include_router(tools.router)
    app.include_router(providers.router)
    app.include_router(chat.router)

    return app


app = create_app()
