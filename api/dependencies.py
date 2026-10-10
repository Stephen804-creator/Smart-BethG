import hmac

from fastapi import Depends, HTTPException, Request, status
from database import get_connection
from services.auth_service import get_user_by_id
from services.task_service import TaskService
from services.agent_service import AgentService
from services.approval_service import ApprovalService
from services.audit_service import AuditService
from services.provider_service import ProviderService
from services.tool_service import ToolService
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
def get_tool_service(): return ToolService()

def require_csrf(request: Request):
    """Validate the synchronizer token for every unsafe cookie-authenticated request."""
    expected = request.session.get("csrf_token")
    supplied = request.headers.get("x-csrf-token", "")
    if not expected or not supplied or not hmac.compare_digest(str(expected), str(supplied)):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="CSRF token missing or invalid.")
    return True


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
    if request.method.upper() not in {"GET", "HEAD", "OPTIONS", "TRACE"}:
        require_csrf(request)
    return user


def get_optional_user(request: Request):
    """Same as get_current_user but returns None instead of raising."""
    user_id = request.session.get("user_id")
    if not user_id:
        return None
    return get_user_by_id(user_id)


def require_role(role: str):
    """
    Dependency factory: `Depends(require_role("admin"))`. Fails closed -
    unknown/missing role is never treated as authorized.
    """
    def _check(user=Depends(get_current_user)):
        if user.get("role") != role:
            raise HTTPException(status_code=403, detail=f"This requires the '{role}' role.")
        return user
    return _check

from services.project_service import ProjectService


def get_project_service():
    return ProjectService()

from services.artifact_service import ArtifactService


def get_artifact_service():
    return ArtifactService()

from services.mission_service import MissionService


def get_mission_service():
    return MissionService()

from services.workflow_service import WorkflowService


def get_workflow_service():
    return WorkflowService()

from services.social_content_service import SocialContentService


def get_social_content_service():
    return SocialContentService()

from services.research_service import ResearchService
from services.evidence_service import EvidenceService


def get_research_service():
    return ResearchService()


def get_evidence_service():
    return EvidenceService()
