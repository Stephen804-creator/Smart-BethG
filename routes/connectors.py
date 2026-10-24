"""Authenticated connector catalog, installations, OAuth and policy-checked actions."""
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field
from api.dependencies import get_current_user, get_connector_installation_service, get_connector_action_service
from services.connector_service import ConnectorRegistry, ConnectorInstallationService
from services.connector_oauth_service import ConnectorOAuthService
import config

def _callback_url(request: Request, provider: str) -> str:
    if config.SMART_BETHG_PUBLIC_BASE_URL:
        return f"{config.SMART_BETHG_PUBLIC_BASE_URL}/connectors/oauth/{provider}/callback"
    return str(request.url_for("connector_oauth_callback", provider=provider))

router = APIRouter(prefix="/connectors", tags=["connectors"])

class InstallRequest(BaseModel):
    connector_key: str = Field(min_length=1, max_length=80)
    label: str | None = Field(default=None, max_length=120)
    permissions: list[str] | None = Field(default=None, max_length=30)

class ActionRequest(BaseModel):
    arguments: dict = Field(default_factory=dict)

@router.get("/catalog")
def catalog(user=Depends(get_current_user)):
    return {"connectors": ConnectorRegistry().catalog()}

@router.get("")
def list_connectors(user=Depends(get_current_user), service=Depends(get_connector_installation_service)):
    return {"connectors": service.list_for_user(user["id"])}

@router.post("")
def install_connector(payload: InstallRequest, user=Depends(get_current_user), service=Depends(get_connector_installation_service)):
    try:
        return service.install(user["id"], payload.connector_key, payload.label, payload.permissions)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))

@router.delete("/{installation_id}")
def disconnect_connector(installation_id: int, user=Depends(get_current_user)):
    if not ConnectorOAuthService().disconnect(user["id"], installation_id):
        raise HTTPException(status_code=404, detail="Connector installation not found.")
    return {"disconnected": True}

@router.post("/{installation_id}/oauth/start")
def start_oauth(installation_id: int, request: Request, user=Depends(get_current_user)):
    installation = ConnectorInstallationService().get_for_user(user["id"], installation_id)
    if not installation:
        raise HTTPException(status_code=404, detail="Connector installation not found.")
    provider = installation["connector_key"]
    callback_url = _callback_url(request, provider)
    try:
        return {"authorization_url": ConnectorOAuthService().start(user["id"], installation_id, provider, callback_url),
                "provider": provider}
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc))

@router.get("/oauth/{provider}/callback", name="connector_oauth_callback")
def oauth_callback(provider: str, request: Request, code: str | None = None,
                   state: str | None = None, error: str | None = None):
    if error:
        return RedirectResponse(url="/?connector_oauth=denied", status_code=303)
    callback_url = _callback_url(request, provider)
    try:
        result = ConnectorOAuthService().callback(provider, code, state, callback_url)
    except ValueError:
        raise HTTPException(status_code=400, detail="Connector authorization state is invalid or expired. Start the connection again.")
    except RuntimeError:
        raise HTTPException(status_code=502, detail="The provider connection failed. Check provider configuration and try again.")
    return RedirectResponse(url="/?connector_oauth=connected&provider=" + result["connector_key"], status_code=303)

@router.post("/{installation_id}/actions/{action}")
def run_connector_action(installation_id: int, action: str, payload: ActionRequest,
                         user=Depends(get_current_user), service=Depends(get_connector_action_service)):
    result = service.request_action(user["id"], installation_id, action, payload.arguments)
    status = result.get("status")
    if status == "not_found":
        raise HTTPException(status_code=404, detail=result.get("detail"))
    if status == "invalid":
        raise HTTPException(status_code=422, detail=result.get("detail"))
    if status == "denied":
        raise HTTPException(status_code=403, detail=result.get("detail"))
    return result
