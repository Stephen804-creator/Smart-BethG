"""Authenticated organization and workspace collaboration APIs."""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from api.dependencies import get_current_user
from services.workspace_service import WorkspaceService

router = APIRouter(prefix="/workspaces", tags=["workspaces"])
service = WorkspaceService()


class OrganizationCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)


class OrganizationMemberInput(BaseModel):
    username: str = Field(min_length=1, max_length=120)
    role: str = Field(default="member", pattern="^(admin|member)$")


class WorkspaceCreate(BaseModel):
    organization_id: int = Field(ge=1)
    name: str = Field(min_length=1, max_length=120)
    description: str = Field(default="", max_length=2000)


class WorkspaceMemberInput(BaseModel):
    username: str = Field(min_length=1, max_length=120)
    role: str = Field(default="viewer", pattern="^(admin|editor|viewer)$")


class DocumentCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    body: str = Field(min_length=1, max_length=100000)


@router.post("/organizations", status_code=201)
def create_organization(payload: OrganizationCreate, user=Depends(get_current_user)):
    try:
        return service.create_organization(user["id"], payload.name)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except Exception as exc:
        if "unique" in str(exc).lower():
            raise HTTPException(status_code=409, detail="An organization with this name already exists.")
        raise


@router.get("/organizations")
def list_organizations(user=Depends(get_current_user)):
    return {"organizations": service.list_organizations(user["id"])}


@router.get("/organizations/{organization_id}")
def get_organization(organization_id: int, user=Depends(get_current_user)):
    item = service.get_organization(user["id"], organization_id)
    if not item:
        raise HTTPException(status_code=404, detail="Organization not found.")
    return item


@router.post("/organizations/{organization_id}/members")
def add_organization_member(organization_id: int, payload: OrganizationMemberInput, user=Depends(get_current_user)):
    try:
        return service.add_organization_member(user["id"], organization_id, payload.username, payload.role)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@router.post("")
def create_workspace(payload: WorkspaceCreate, user=Depends(get_current_user)):
    try:
        return service.create_workspace(user["id"], payload.organization_id, payload.name, payload.description)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except Exception as exc:
        if "unique" in str(exc).lower():
            raise HTTPException(status_code=409, detail="A workspace with this name already exists in the organization.")
        raise


@router.get("")
def list_workspaces(organization_id: int | None = None, user=Depends(get_current_user)):
    return {"workspaces": service.list_workspaces(user["id"], organization_id)}


@router.get("/{workspace_id}")
def get_workspace(workspace_id: int, user=Depends(get_current_user)):
    item = service.get_workspace(user["id"], workspace_id)
    if not item:
        raise HTTPException(status_code=404, detail="Workspace not found.")
    return item


@router.post("/{workspace_id}/members")
def add_workspace_member(workspace_id: int, payload: WorkspaceMemberInput, user=Depends(get_current_user)):
    try:
        return service.add_workspace_member(user["id"], workspace_id, payload.username, payload.role)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@router.get("/{workspace_id}/documents")
def list_workspace_documents(workspace_id: int, user=Depends(get_current_user)):
    try:
        return {"documents": service.list_documents(user["id"], workspace_id)}
    except LookupError:
        raise HTTPException(status_code=404, detail="Workspace not found.")


@router.post("/{workspace_id}/documents", status_code=201)
def create_workspace_document(workspace_id: int, payload: DocumentCreate, user=Depends(get_current_user)):
    try:
        return service.create_document(user["id"], workspace_id, payload.title, payload.body)
    except LookupError:
        raise HTTPException(status_code=404, detail="Workspace not found.")
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@router.patch("/{workspace_id}/documents/{document_id}")
def update_workspace_document(workspace_id: int, document_id: int, payload: DocumentCreate, user=Depends(get_current_user)):
    try:
        item = service.update_document(user["id"], workspace_id, document_id, payload.title, payload.body)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    if not item:
        raise HTTPException(status_code=404, detail="Workspace document not found.")
    return item
