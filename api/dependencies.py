from fastapi import HTTPException, Request, status
from database import get_connection
from services.auth_service import get_user_by_id
from services.task_service import TaskService
from services.agent_service import AgentService
from services.approval_service import ApprovalService
from services.audit_service import AuditService
from services.provider_service import ProviderService
from controller import Controller

_controller = None

def get_controller():
    global _controller
    if _controller is None:
        _controller = Controller()
    return _controller

def get_task_service(): return TaskService()
def get_agent_service(): return AgentService()
def get_approval_service(): return ApprovalService()
def get_audit_service(): return AuditService()
def get_provider_service(): return ProviderService()

def get_current_user(request: Request):
    """
    Resolve the authenticated user from the signed session cookie.

    This deliberately does NOT trust any client-supplied header (an
    earlier version trusted an X-User-Id header, which allowed any caller
    to impersonate any user id - that was a real vulnerability, not a
    placeholder). The session is set by /auth/login and signed with
    SECRET_KEY via Starlette's SessionMiddleware, so it cannot be forged
    by the client.
    """
    user_id = request.session.get("user_id")
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required.")
    user = get_user_by_id(user_id)
    if not user:
        request.session.clear()
        raise HTTPException(status_code=401, detail="Invalid or inactive user.")
    return user


def get_optional_user(request: Request):
    """Same as get_current_user but returns None instead of raising."""
    user_id = request.session.get("user_id")
    if not user_id:
        return None
    return get_user_by_id(user_id)
