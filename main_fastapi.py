from fastapi import FastAPI
from api.routes import health,auth,tasks,agents,approvals,audit,tools,providers
from database import initialize_database

def create_app():
    initialize_database()
    app=FastAPI(title="Smart BethG",version="1.0.0")
    for module in [health,auth,tasks,agents,approvals,audit,tools,providers]: app.include_router(module.router)
    return app
app=create_app()
