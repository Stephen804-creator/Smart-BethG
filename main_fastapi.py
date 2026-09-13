"""
Smart BethG
FastAPI Application Entry Point
"""

from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

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
    workspace,
)


BASE_DIR = Path(__file__).resolve().parent
TEMPLATES_DIR = BASE_DIR / "templates"
STATIC_DIR = BASE_DIR / "static"


templates = Jinja2Templates(
    directory=str(TEMPLATES_DIR)
)


def create_app() -> FastAPI:
    """
    Create and configure the Smart BethG application.
    """

    initialize_database()

    app = FastAPI(
        title="Smart BethG",
        version="1.0.0",
        description="Smart BethG AI Agent Platform",
    )

    # ---------------------------------------------------------
    # Static files
    # ---------------------------------------------------------
    #
    # This makes:
    #
    # /static/css/main.css
    # /static/js/app.js
    #
    # available to the browser.
    #
    app.mount(
        "/static",
        StaticFiles(directory=str(STATIC_DIR)),
        name="static",
    )

    # ---------------------------------------------------------
    # Smart BethG Home
    # ---------------------------------------------------------

    @app.get(
        "/",
        response_class=HTMLResponse,
        include_in_schema=False,
    )
    async def home(request: Request):
        """
        Render the Smart BethG workspace.
        """

        return templates.TemplateResponse(
            request=request,
            name="index.html",
            context={
                "app_version": "1.0.0",
            },
        )

    # ---------------------------------------------------------
    # Existing backend routers
    # ---------------------------------------------------------

    app.include_router(health.router)
    app.include_router(auth.router)
    app.include_router(tasks.router)
    app.include_router(agents.router)
    app.include_router(approvals.router)
    app.include_router(audit.router)
    app.include_router(tools.router)
    app.include_router(providers.router)
    app.include_router(workspace.router)

    return app


app = create_app()
