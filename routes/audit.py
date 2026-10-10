from fastapi import APIRouter, Depends

from api.dependencies import get_current_user, get_audit_service, require_role

router = APIRouter(prefix="/audit", tags=["audit"])


@router.get("")
def audit(user=Depends(get_current_user), service=Depends(get_audit_service)):
    return service.list_events(user["id"])


@router.get("/all")
def audit_all(user=Depends(require_role("admin")), service=Depends(get_audit_service)):
    """
    Admin-only: audit events across every user. Uses the require_role
    dependency that existed since the authorization work but had never
    actually been applied to a real endpoint until now.
    """
    return service.list_all_events()
