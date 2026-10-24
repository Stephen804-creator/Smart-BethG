"""Authenticated connector catalog, installations, and policy-checked actions."""
from fastapi import APIRouter,Depends,HTTPException
from pydantic import BaseModel,Field
from api.dependencies import get_current_user,get_connector_installation_service,get_connector_action_service
from services.connector_service import ConnectorRegistry

router=APIRouter(prefix="/connectors",tags=["connectors"])

class InstallRequest(BaseModel):
    connector_key:str=Field(min_length=1,max_length=80)
    label:str|None=Field(default=None,max_length=120)
    permissions:list[str]|None=Field(default=None,max_length=30)

class ActionRequest(BaseModel):
    arguments:dict=Field(default_factory=dict)

@router.get("/catalog")
def catalog(user=Depends(get_current_user)):
    return {"connectors":ConnectorRegistry().catalog()}

@router.get("")
def list_connectors(user=Depends(get_current_user),service=Depends(get_connector_installation_service)):
    return {"connectors":service.list_for_user(user["id"])}

@router.post("")
def install_connector(payload:InstallRequest,user=Depends(get_current_user),service=Depends(get_connector_installation_service)):
    try: return service.install(user["id"],payload.connector_key,payload.label,payload.permissions)
    except ValueError as exc: raise HTTPException(status_code=422,detail=str(exc))

@router.delete("/{installation_id}")
def disconnect_connector(installation_id:int,user=Depends(get_current_user),service=Depends(get_connector_installation_service)):
    if not service.disconnect(user["id"],installation_id): raise HTTPException(status_code=404,detail="Connector installation not found.")
    return {"disconnected":True}

@router.post("/{installation_id}/actions/{action}")
def run_connector_action(installation_id:int,action:str,payload:ActionRequest,user=Depends(get_current_user),service=Depends(get_connector_action_service)):
    result=service.request_action(user["id"],installation_id,action,payload.arguments)
    status=result.get("status")
    if status=="not_found": raise HTTPException(status_code=404,detail=result.get("detail"))
    if status=="invalid": raise HTTPException(status_code=422,detail=result.get("detail"))
    if status=="denied": raise HTTPException(status_code=403,detail=result.get("detail"))
    return result
