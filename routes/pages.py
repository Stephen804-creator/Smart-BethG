import os

from fastapi import APIRouter, Form, Request
from fastapi.responses import RedirectResponse, FileResponse
from urllib.parse import urlencode

from api.dependencies import get_optional_user
from providers.provider_manager import provider_manager
from database import get_connection

router = APIRouter(tags=["pages"])


def _templates(request: Request):
    return request.app.state.templates


def _require_user(request: Request):
    """Return the logged-in user, or None. Callers redirect if None."""
    return get_optional_user(request)


def _real_system_status():
    """
    Status values computed from actual checks - not hardcoded/decorative.
    """
    status = []

    try:
        conn = get_connection()
        conn.execute("SELECT 1")
        conn.close()
        status.append({"name": "Database", "status": "success"})
    except Exception:
        status.append({"name": "Database", "status": "error"})

    ai_ok = provider_manager.default_provider_name() is not None
    status.append({"name": "AI provider", "status": "success" if ai_ok else "warning"})

    return status


def _real_capabilities():
    """
    Only lists capabilities that are actually wired up right now.
    Deliberately does not list research, artifacts, workflows, etc. -
    those have storage tables but no functional implementation yet.
    """
    return [
        {
            "name": "Chat",
            "description": "Have a real conversation with Smart BethG.",
            "status": "active",
            "icon": "fa-solid fa-comments",
            "action": "open-chat",
        }
    ]


@router.get("/", name="main.home")
def home(request: Request):
    user = _require_user(request)
    if not user:
        return RedirectResponse("/login", status_code=302)

    return _templates(request).TemplateResponse(
        "index.html",
        {
            "request": request,
            "app_version": "1.0.0",
            "quick_actions": None,
            "capabilities": _real_capabilities(),
            "missions": None,
            "artifacts": None,
            "notifications": None,
            "recent_activity": None,
            "system_status": _real_system_status(),
            "error_message": None,
        },
    )


@router.get("/chat", name="main.chat_page")
def chat_page(request: Request):
    user = _require_user(request)
    if not user:
        return RedirectResponse("/login", status_code=302)
    return _templates(request).TemplateResponse("chat.html", {"request": request})


@router.post("/chat", name="main.chat")
def chat_quick_submit(request: Request, prompt: str = Form(...)):
    """
    Handles the home page's quick-assistant box. It does not fabricate a
    response inline - it hands the prompt to the real chat page, which
    sends it through the actual /api/chat endpoint.
    """
    user = _require_user(request)
    if not user:
        return RedirectResponse("/login", status_code=302)
    query = urlencode({"prompt": prompt})
    return RedirectResponse(f"/chat?{query}", status_code=302)


@router.get("/service-worker.js", name="main.service_worker")
def service_worker():
    """
    Served from the root path (not /static/service-worker.js) so its
    default scope covers the whole app - a service worker's scope is
    limited to its own directory and below unless a
    Service-Worker-Allowed header says otherwise.
    """
    static_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "static")
    return FileResponse(os.path.join(static_dir, "service-worker.js"), media_type="application/javascript")


@router.get("/login", name="main.login")
def login_page(request: Request):
    if _require_user(request):
        return RedirectResponse("/", status_code=302)
    return _templates(request).TemplateResponse("login.html", {"request": request})
