from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import RedirectResponse

import config
from services.auth_service import find_or_create_oauth_user
from services.rate_limiter import check_rate_limit
from logging_setup import get_logger

logger = get_logger("auth")

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
    client_ip = request.client.host if request.client else "unknown"
    if not check_rate_limit(f"oauth-callback:{client_ip}"):
        raise HTTPException(status_code=429, detail="Too many sign-in attempts. Please wait and try again.")
    if not config.GOOGLE_OAUTH_ENABLED:
        raise HTTPException(status_code=503, detail="Google Sign-In isn't configured on this deployment.")

    try:
        token = await _get_oauth().google.authorize_access_token(request)
    except Exception:
        logger.warning("Google sign-in callback failed for client=%s", client_ip, exc_info=True)
        raise HTTPException(status_code=400, detail="Google sign-in failed. Please try again.")

    userinfo = token.get("userinfo") or {}
    email = userinfo.get("email")
    subject = userinfo.get("sub")
    if not email or not subject or userinfo.get("email_verified") is not True:
        raise HTTPException(status_code=400, detail="Google did not return a verified account email.")

    try:
        user = find_or_create_oauth_user(
            email, "google", subject, allow_create=config.REGISTRATION_OPEN
        )
    except PermissionError:
        raise HTTPException(
            status_code=403,
            detail="Registration is closed. Use an existing linked account or password sign-in.",
        )
    request.session["user_id"] = user["id"]
    return RedirectResponse("/", status_code=302)
