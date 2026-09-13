"""
Smart BethG
FastAPI Application Entry Point
"""

from fastapi import FastAPI

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
)


def create_app() -> FastAPI:
    """
    Create and configure the Smart BethG FastAPI application.
    """

    initialize_database()

    app = FastAPI(
        title="Smart BethG",
        version="1.0.0",
        description="Smart BethG AI Agent Platform API",
    )

    app.include_router(health.router)
    app.include_router(auth.router)
    app.include_router(tasks.router)
    app.include_router(agents.router)
    app.include_router(approvals.router)
    app.include_router(audit.router)
    app.include_router(tools.router)
    app.include_router(providers.router)

    return app


app = create_app()
