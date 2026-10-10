from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import RedirectResponse

import config
from services.auth_service import find_or_create_oauth_user

router = APIRouter(prefix="/auth/google", tags=["auth"])

_oauth = None


def _get_oauth():
    """
    Lazily construct the Authlib OAuth client. Only imported/constructed
    when actually configured, so a deployment with no Google OAuth
    credentials never touches Authlib at all - consistent with every
    other "not configured" path in this app being honest rather than
    crashing.
    """
    global _oauth
    if _oauth is None:
        from authlib.integrations.starlette_client import OAuth

        _oauth = OAuth()
        _oauth.register(
            name="google",
            client_id=config.GOOGLE_OAUTH_CLIENT_ID,
            client_secret=config.GOOGLE_OAUTH_CLIENT_SECRET,
            server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
            client_kwargs={"scope": "openid email profile"},
        )
    return _oauth


@router.get("/login", name="main.google_login")
async def google_login(request: Request):
    if not config.GOOGLE_OAUTH_ENABLED:
        raise HTTPException(
            status_code=503,
            detail="Google Sign-In isn't configured on this deployment yet "
            "(GOOGLE_OAUTH_CLIENT_ID / GOOGLE_OAUTH_CLIENT_SECRET are not set).",
        )
    redirect_uri = request.url_for("main.google_callback")
    return await _get_oauth().google.authorize_redirect(request, str(redirect_uri))


@router.get("/callback", name="main.google_callback")
async def google_callback(request: Request):
    if not config.GOOGLE_OAUTH_ENABLED:
        raise HTTPException(status_code=503, detail="Google Sign-In isn't configured on this deployment.")

    try:
        token = await _get_oauth().google.authorize_access_token(request)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Google sign-in failed: {exc}")

    userinfo = token.get("userinfo") or {}
    email = userinfo.get("email")
    subject = userinfo.get("sub")
    if not email or not subject:
        raise HTTPException(status_code=400, detail="Google did not return the expected account details.")

    user = find_or_create_oauth_user(email, "google", subject)
    request.session["user_id"] = user["id"]
    return RedirectResponse("/", status_code=302)
