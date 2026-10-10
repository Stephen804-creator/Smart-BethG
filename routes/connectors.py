"""Authenticated connector catalog and connection-status API."""
from fastapi import APIRouter, Depends

from api.dependencies import get_current_user
from connectors.social import SocialConnectorRegistry
from database import get_connection

router = APIRouter(prefix="/connectors", tags=["connectors"])


@router.get("")
def list_connectors(_user=Depends(get_current_user)):
    return {"connectors": SocialConnectorRegistry().catalog()}


@router.get("/social-accounts")
def list_social_accounts(user=Depends(get_current_user)):
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT id, platform, external_account_id, display_name, scopes_json, status, "
            "connected_at, last_validated_at, created_at, updated_at "
            "FROM social_connections WHERE user_id=? ORDER BY platform, id",
            (user["id"],),
        ).fetchall()
        import json
        accounts = []
        for row in rows:
            item = dict(row)
            try:
                item["scopes"] = json.loads(item.pop("scopes_json") or "[]")
            except (TypeError, json.JSONDecodeError):
                item["scopes"] = []
            accounts.append(item)
        return {"accounts": accounts}
    finally:
        conn.close()
