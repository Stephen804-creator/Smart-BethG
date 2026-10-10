"""Authenticated connector catalog and OAuth-managed social account connections."""
import hmac
import json
import logging
import os
import secrets
from datetime import datetime, timezone
from urllib.parse import urlencode

import requests
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse

from api.dependencies import get_current_user
from connectors.social import ConnectorNotConfigured, SocialConnectorRegistry
from database import get_connection
from services.credential_vault import CredentialVault, CredentialVaultError

logger = logging.getLogger("smart_bethg.connectors")
router = APIRouter(prefix="/connectors", tags=["connectors"])

META_SCOPES = ("pages_show_list", "pages_read_engagement", "pages_manage_posts")


def _meta_config():
    return {
        "app_id": os.getenv("SMART_BETHG_META_APP_ID", "").strip(),
        "app_secret": os.getenv("SMART_BETHG_META_APP_SECRET", "").strip(),
        "redirect_uri": os.getenv("SMART_BETHG_META_REDIRECT_URI", "").strip(),
        "api_version": os.getenv("SMART_BETHG_META_API_VERSION", "v26.0").strip(),
    }


def _meta_ready_for_oauth(settings):
    return bool(settings["app_id"] and settings["app_secret"] and settings["redirect_uri"])


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


@router.get("/meta/configuration")
def meta_configuration(_user=Depends(get_current_user)):
    settings = _meta_config()
    return {
        "oauth_configured": _meta_ready_for_oauth(settings),
        "publishing_enabled": os.getenv("SMART_BETHG_META_PUBLISHING_ENABLED", "").strip().lower() == "true",
    }


@router.get("/meta/start")
def start_meta_oauth(request: Request, user=Depends(get_current_user)):
    settings = _meta_config()
    if not _meta_ready_for_oauth(settings):
        raise HTTPException(
            status_code=503,
            detail="Meta OAuth is not configured. Set the app ID, app secret, and registered redirect URI.",
        )
    state = secrets.token_urlsafe(32)
    request.session["meta_oauth_state"] = state
    request.session["meta_oauth_user_id"] = int(user["id"])
    query = urlencode({
        "client_id": settings["app_id"],
        "redirect_uri": settings["redirect_uri"],
        "state": state,
        "response_type": "code",
        "scope": ",".join(META_SCOPES),
    })
    return RedirectResponse(
        f"https://www.facebook.com/{settings['api_version']}/dialog/oauth?{query}",
        status_code=302,
    )


@router.get("/meta/callback")
def finish_meta_oauth(request: Request, user=Depends(get_current_user)):
    expected_state = request.session.pop("meta_oauth_state", None)
    expected_user_id = request.session.pop("meta_oauth_user_id", None)
    received_state = request.query_params.get("state", "")
    if (
        not expected_state
        or not received_state
        or not hmac.compare_digest(str(expected_state), str(received_state))
        or expected_user_id != int(user["id"])
    ):
        return RedirectResponse("/social?meta=state_error", status_code=303)
    if request.query_params.get("error") or not request.query_params.get("code"):
        return RedirectResponse("/social?meta=cancelled", status_code=303)

    settings = _meta_config()
    if not _meta_ready_for_oauth(settings):
        return RedirectResponse("/social?meta=not_configured", status_code=303)
    version = settings["api_version"]
    created_refs = []
    old_refs = []
    conn = None
    try:
        token_response = requests.get(
            f"https://graph.facebook.com/{version}/oauth/access_token",
            params={
                "client_id": settings["app_id"],
                "client_secret": settings["app_secret"],
                "redirect_uri": settings["redirect_uri"],
                "code": request.query_params["code"],
            },
            timeout=15,
        )
        token_response.raise_for_status()
        short_token = token_response.json().get("access_token")
        if not short_token:
            return RedirectResponse("/social?meta=token_error", status_code=303)

        long_response = requests.get(
            f"https://graph.facebook.com/{version}/oauth/access_token",
            params={
                "grant_type": "fb_exchange_token",
                "client_id": settings["app_id"],
                "client_secret": settings["app_secret"],
                "fb_exchange_token": short_token,
            },
            timeout=15,
        )
        long_response.raise_for_status()
        user_token_data = long_response.json()
        user_token = user_token_data.get("access_token") or short_token
        if not user_token:
            return RedirectResponse("/social?meta=token_error", status_code=303)

        permission_response = requests.get(
            f"https://graph.facebook.com/{version}/me/permissions",
            headers={"Authorization": "Bearer " + user_token},
            timeout=15,
        )
        permission_response.raise_for_status()
        granted = {
            entry.get("permission")
            for entry in permission_response.json().get("data", [])
            if entry.get("status") == "granted"
        }
        if not set(META_SCOPES).issubset(granted):
            return RedirectResponse("/social?meta=permissions_missing", status_code=303)

        pages_response = requests.get(
            f"https://graph.facebook.com/{version}/me/accounts",
            params={"fields": "id,name,access_token,tasks"},
            headers={"Authorization": "Bearer " + user_token},
            timeout=15,
        )
        pages_response.raise_for_status()
        pages = pages_response.json().get("data", [])
        eligible = [
            page for page in pages
            if page.get("id") and page.get("access_token")
            and any(task in {"CREATE_CONTENT", "MANAGE", "ADMINISTER"} for task in page.get("tasks", []))
        ]
        if not eligible:
            return RedirectResponse("/social?meta=no_pages", status_code=303)

        vault = CredentialVault()
        conn = get_connection()
        stored = 0
        for page in eligible:
            page_id = str(page["id"])
            existing = conn.execute(
                "SELECT id, credential_ref FROM social_connections "
                "WHERE user_id=? AND platform='facebook' AND external_account_id=? LIMIT 1",
                (user["id"], page_id),
            ).fetchone()
            if existing and existing["credential_ref"]:
                old_refs.append(existing["credential_ref"])
            credential_ref = vault.store(
                user["id"], "meta", page["access_token"], scopes=list(META_SCOPES), connection=conn,
            )
            created_refs.append(credential_ref)
            if existing:
                conn.execute(
                    "UPDATE social_connections SET display_name=?, credential_ref=?, scopes_json=?, "
                    "status='pending', connected_at=NULL, last_validated_at=NULL, updated_at=CURRENT_TIMESTAMP "
                    "WHERE id=? AND user_id=?",
                    (str(page.get("name") or "Facebook Page")[:200], credential_ref,
                     json.dumps(list(META_SCOPES)), existing["id"], user["id"]),
                )
            else:
                conn.execute(
                    "INSERT INTO social_connections(user_id, platform, external_account_id, display_name, "
                    "credential_ref, scopes_json, status, updated_at) "
                    "VALUES (?, 'facebook', ?, ?, ?, ?, 'pending', CURRENT_TIMESTAMP)",
                    (user["id"], page_id, str(page.get("name") or "Facebook Page")[:200],
                     credential_ref, json.dumps(list(META_SCOPES))),
                )
            stored += 1
        conn.commit()
        for old_reference in old_refs:
            try:
                vault.revoke(old_reference, user["id"], "meta")
            except CredentialVaultError:
                logger.warning("Could not revoke replaced Meta credential for user_id=%s", user["id"])
        return RedirectResponse(f"/social?meta=pending&accounts={stored}", status_code=303)
    except CredentialVaultError:
        if conn:
            conn.rollback()
        for reference in created_refs:
            try:
                CredentialVault().revoke(reference, user["id"], "meta")
            except Exception:
                pass
        return RedirectResponse("/social?meta=vault_not_configured", status_code=303)
    except Exception:
        if conn:
            conn.rollback()
        for reference in created_refs:
            try:
                CredentialVault().revoke(reference, user["id"], "meta")
            except Exception:
                pass
        # Do not log exception messages: provider exceptions may contain sensitive
        # request details. Keep only the owner ID and a generic event.
        logger.warning("Meta OAuth callback failed for user_id=%s", user["id"])
        return RedirectResponse("/social?meta=provider_error", status_code=303)
    finally:
        if conn:
            conn.close()


@router.post("/social-accounts/{connection_id}/activate")
def activate_social_account(connection_id: int, user=Depends(get_current_user)):
    conn = get_connection()
    try:
        account = conn.execute(
            "SELECT id, platform, external_account_id, credential_ref, status FROM social_connections "
            "WHERE id=? AND user_id=? LIMIT 1",
            (connection_id, user["id"]),
        ).fetchone()
        if not account:
            raise HTTPException(status_code=404, detail="Social account not found.")
        if account["platform"] != "facebook":
            raise HTTPException(status_code=409, detail="This account activation flow is not implemented for the selected platform.")
        if not account["credential_ref"]:
            raise HTTPException(status_code=409, detail="Account has no credential reference.")
        # Verify both decryption and the live Page token before activating the
        # account. This does not enable publishing; the publisher adapter is a
        # separate, explicit operator-controlled setting.
        try:
            token = CredentialVault().resolve(account["credential_ref"], user["id"], "meta")
        except CredentialVaultError as exc:
            raise HTTPException(status_code=409, detail="Stored account credential is unavailable. Reconnect the account.") from exc
        settings = _meta_config()
        try:
            verification = requests.get(
                f"https://graph.facebook.com/{settings['api_version']}/{account['external_account_id']}",
                params={"fields": "id,name"},
                headers={"Authorization": "Bearer " + token},
                timeout=15,
            )
            verification.raise_for_status()
            verified_page = verification.json()
        except Exception:
            raise HTTPException(status_code=502, detail="Meta could not verify this Page token. Reconnect the account.")
        if str(verified_page.get("id", "")) != str(account["external_account_id"]):
            raise HTTPException(status_code=409, detail="Meta returned a different Page identity.")
        conn.execute(
            "UPDATE social_connections SET status='active', connected_at=CURRENT_TIMESTAMP, "
            "last_validated_at=CURRENT_TIMESTAMP, updated_at=CURRENT_TIMESTAMP "
            "WHERE id=? AND user_id=?",
            (connection_id, user["id"]),
        )
        try:
            SocialConnectorRegistry().get_publisher(account["platform"])
            publisher_ready = True
        except ConnectorNotConfigured:
            publisher_ready = False
        if publisher_ready:
            conn.execute(
                "UPDATE social_publish_jobs SET status='queued', connection_id=?, error_code=NULL, "
                "error_message=NULL, updated_at=CURRENT_TIMESTAMP "
                "WHERE user_id=? AND platform=? AND status IN ('awaiting_connection','blocked') "
                "AND error_code IN ('connection_revoked','connection_required','connector_not_configured') "
                "AND content_id IN (SELECT s.id FROM social_content s "
                "JOIN social_campaigns c ON c.id=s.campaign_id AND c.user_id=s.user_id "
                "WHERE s.user_id=? AND s.platform=? AND s.status='approved' AND c.status='active')",
                (connection_id, user["id"], account["platform"], user["id"], account["platform"]),
            )
        conn.commit()
        return {"activated": True, "connection_id": connection_id, "platform": account["platform"]}
    finally:
        conn.close()


@router.delete("/social-accounts/{connection_id}")
def disconnect_social_account(connection_id: int, user=Depends(get_current_user)):
    conn = get_connection()
    try:
        account = conn.execute(
            "SELECT id, platform, credential_ref FROM social_connections WHERE id=? AND user_id=? LIMIT 1",
            (connection_id, user["id"]),
        ).fetchone()
        if not account:
            raise HTTPException(status_code=404, detail="Social account not found.")
        provider = "meta" if account["platform"] in {"facebook", "instagram"} else account["platform"]
        try:
            CredentialVault().revoke(account["credential_ref"], user["id"], provider)
        except CredentialVaultError:
            # Mark the account revoked even if the encryption key was rotated or
            # is unavailable; never leave it eligible for future publication.
            pass
        conn.execute(
            "UPDATE social_connections SET status='revoked', updated_at=CURRENT_TIMESTAMP "
            "WHERE id=? AND user_id=?",
            (connection_id, user["id"]),
        )
        conn.execute(
            "UPDATE social_publish_jobs SET status='blocked', error_code='connection_revoked', "
            "error_message='The user disconnected this account.', updated_at=CURRENT_TIMESTAMP "
            "WHERE user_id=? AND connection_id=? AND status IN ('queued','awaiting_connection')",
            (user["id"], connection_id),
        )
        conn.execute(
            "UPDATE social_publish_jobs SET status='cancel_requested', updated_at=CURRENT_TIMESTAMP "
            "WHERE user_id=? AND connection_id=? AND status='publishing'",
            (user["id"], connection_id),
        )
        conn.commit()
        return {"disconnected": True, "connection_id": connection_id}
    finally:
        conn.close()
