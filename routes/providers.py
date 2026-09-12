from fastapi import APIRouter,Depends
from api.dependencies import get_current_user,get_provider_service
router=APIRouter(prefix="/providers",tags=["providers"])
@router.get("")
def providers(user=Depends(get_current_user),service=Depends(get_provider_service)): return service.list_providers(user["id"])
