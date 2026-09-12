from fastapi import Header, HTTPException, status
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

def get_current_user(x_user_id: str | None = Header(default=None)):
    if not x_user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required.")
    try: user_id=int(x_user_id)
    except ValueError: raise HTTPException(status_code=401, detail="Invalid user identifier.")
    user=get_user_by_id(user_id)
    if not user: raise HTTPException(status_code=401, detail="Invalid or inactive user.")
    return user
