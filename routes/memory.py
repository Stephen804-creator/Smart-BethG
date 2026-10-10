from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from api.dependencies import get_current_user
from services.memory_service import MemoryService

router = APIRouter(prefix="/memory", tags=["memory"])


def get_memory_service():
    return MemoryService()


class MemoryCreate(BaseModel):
    content: str = Field(min_length=1, max_length=10000)
    scope: str = Field(default="user", min_length=1, max_length=40)
    scope_ref: str | None = Field(default=None, max_length=200)


@router.get("")
def list_memory(user=Depends(get_current_user), service: MemoryService = Depends(get_memory_service)):
    """Governance view (T0806): everything remembered about this user, across every scope."""
    return {"memory": service.list_all(user["id"])}


@router.post("")
def create_memory(
    payload: MemoryCreate,
    user=Depends(get_current_user),
    service: MemoryService = Depends(get_memory_service),
):
    try:
        return service.remember(
            user["id"], payload.content, scope=payload.scope, scope_ref=payload.scope_ref, source="api"
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.delete("/{memory_id}")
def delete_memory(memory_id: int, user=Depends(get_current_user), service: MemoryService = Depends(get_memory_service)):
    deleted = service.forget(user["id"], memory_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Memory entry not found.")
    return {"deleted": True}


@router.delete("")
def delete_all_memory(user=Depends(get_current_user), service: MemoryService = Depends(get_memory_service)):
    """Right-to-be-forgotten: clears everything remembered about this user."""
    count = service.forget_all(user["id"])
    return {"deleted_count": count}
