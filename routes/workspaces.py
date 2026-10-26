"""Authenticated organization and workspace APIs."""
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from api.dependencies import get_current_user
from services.workspace_service import WorkspaceService

router = APIRouter(prefix="/workspaces", tags=["workspaces"])
service = WorkspaceService()


class OrganizationCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    slug: str = Field(min_length=3, max_length=60)
    default_workspace_name: str = Field(default="General", min_length=1, max_length=120)
    default_workspace_slug: str = Field(default="general", min_length=3, max_length=60)


class WorkspaceCreate(BaseModel):
    organization_id: int = Field(ge=1)
    name: str = Field(min_length=1, max_length=120)
    slug: str = Field(min_length=3, max_length=60)


class MemberGrant(BaseModel):
    username: str = Field(min_length=1, max_length=254)
    role: str = Field(min_length=1, max_length=20)


class AccessCheck(BaseModel):
    permission: str = Field(default="view", max_length=30)


def _raise(exc):
    if isinstance(exc, PermissionError):
        raise HTTPException(status_code=403, detail=str(exc))
    if isinstance(exc, LookupError):
        raise HTTPException(status_code=404, detail=str(exc))
    if isinstance(exc, ValueError):
        raise HTTPException(status_code=422, detail=str(exc))
    if "duplicate key" in str(exc).lower() or "unique constraint" in str(exc).lower():
        raise HTTPException(status_code=409, detail="That organization or workspace slug is already in use.")
    raise exc


@router.post("/organizations")
def create_organization(payload: OrganizationCreate, user=Depends(get_current_user)):
    try:
        return service.create_organization(user["id"], payload.name, payload.slug,
                                            payload.default_workspace_name, payload.default_workspace_slug)
    except Exception as exc:
        _raise(exc)


@router.get("/organizations")
def list_organizations(user=Depends(get_current_user)):
    return {"organizations": service.list_organizations(user["id"])}


@router.get("/organizations/{organization_id}/members")
def list_organization_members(organization_id: int, user=Depends(get_current_user)):
    try:
        return {"members": service.list_organization_members(user["id"], organization_id)}
    except Exception as exc:
        _raise(exc)


@router.post("/organizations/{organization_id}/members")
def add_organization_member(organization_id: int, payload: MemberGrant, user=Depends(get_current_user)):
    try:
        return service.add_organization_member(user["id"], organization_id, payload.username, payload.role)
    except Exception as exc:
        _raise(exc)


@router.get("")
def list_workspaces(organization_id: int | None = Query(default=None, ge=1), user=Depends(get_current_user)):
    try:
        return {"workspaces": service.list_workspaces(user["id"], organization_id)}
    except Exception as exc:
        _raise(exc)


@router.post("")
def create_workspace(payload: WorkspaceCreate, user=Depends(get_current_user)):
    try:
        return service.create_workspace(user["id"], payload.organization_id, payload.name, payload.slug)
    except Exception as exc:
        _raise(exc)


@router.post("/{workspace_id}/members")
def add_workspace_member(workspace_id: int, payload: MemberGrant, user=Depends(get_current_user)):
    try:
        return service.add_workspace_member(user["id"], workspace_id, payload.username, payload.role)
    except Exception as exc:
        _raise(exc)


@router.post("/{workspace_id}/access-check")
def check_workspace_access(workspace_id: int, payload: AccessCheck, user=Depends(get_current_user)):
    try:
        return service.require_workspace_access(user["id"], workspace_id, payload.permission)
    except Exception as exc:
        _raise(exc)
