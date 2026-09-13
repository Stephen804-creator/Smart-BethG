from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles


BASE_DIR = Path(__file__).resolve().parent
TEMPLATES_DIR = BASE_DIR / "templates"
STATIC_DIR = BASE_DIR / "static"


app = FastAPI(
    title="Smart-BethG",
    description="Smart-BethG AI Work Agent",
    version="1.0.0",
)


app.mount(
    "/static",
    StaticFiles(directory=STATIC_DIR),
    name="static",
)


@app.get("/")
async def home():
    return FileResponse(TEMPLATES_DIR / "index.html")


@app.get("/health")
async def health():
    return {
        "status": "online",
        "service": "Smart-BethG",
    }
