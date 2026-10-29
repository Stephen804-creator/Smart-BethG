import secrets

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field, field_validator

import config
from services.auth_service import authenticate_user, create_user, revoke_user_sessions
from services.rate_limiter import check_rate_limit
from api.dependencies import get_current_user, require_csrf
from logging_setup import get_logger

router = APIRouter(prefix="/auth", tags=["auth"])
logger = get_logger("auth")


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=254)
    password: str = Field(min_length=1, max_length=1024)


class RegisterRequest(BaseModel):
    username: str = Field(min_length=1, max_length=254)
    password: str = Field(min_length=8, max_length=1024)

    @field_validator("username")
    @classmethod
    def username_not_blank(cls, v):
        if not v or not v.strip():
            raise ValueError("Username is required.")
        return v.strip()


def _client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


@router.get("/csrf")
def csrf_token(request: Request, response: Response):
    token = request.session.get("csrf_token")
    if not token:
        token = secrets.token_urlsafe(32)
        request.session["csrf_token"] = token
    response.headers["Cache-Control"] = "no-store"
    return {"csrf_token": token}


@router.post("/login")
def login(payload: LoginRequest, request: Request, _csrf=Depends(require_csrf)):
    if not check_rate_limit(f"login:{_client_ip(request)}"):
        logger.warning("Login rate-limited for %s", _client_ip(request))
        raise HTTPException(status_code=429, detail="Too many login attempts. Please wait and try again.")

    user = authenticate_user(payload.username, payload.password)
    if not user:
        logger.info("Failed login attempt")
        return {"authenticated": False, "error": "Invalid credentials."}
    request.session.clear()
    request.session["user_id"] = user["id"]
    request.session["session_version"] = user["session_version"]
    csrf = secrets.token_urlsafe(32)
    request.session["csrf_token"] = csrf
    logger.info("User %s logged in", user["id"])
    return {"authenticated": True, "user": user, "csrf_token": csrf}


@router.post("/logout")
def logout(request: Request, _csrf=Depends(require_csrf)):
    user_id = request.session.get("user_id")
    if user_id:
        # Increment the server-side version so copied signed cookies cannot
        # continue authenticating after logout.
        revoke_user_sessions(user_id)
    request.session.clear()
    logger.info("User %s logged out; prior sessions revoked", user_id)
    return {"authenticated": False}


@router.post("/register")
def register(payload: RegisterRequest, request: Request, _csrf=Depends(require_csrf)):
    """
    Public self-registration is always open; rate limits and password validation apply.
    """
    if not check_rate_limit(f"register:{_client_ip(request)}"):
        logger.warning("Registration rate-limited for %s", _client_ip(request))
        raise HTTPException(status_code=429, detail="Too many attempts. Please wait and try again.")

    try:
        user = create_user(payload.username, payload.password)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    if user is None:
        raise HTTPException(status_code=409, detail="That username is already taken.")
    logger.info("New user registered: %s", user["id"])
    return {"created": True, "user": user}


@router.get("/config")
def auth_config():
    """Lets the frontend know which sign-in options are actually usable."""
    return {
        "google_oauth_enabled": config.GOOGLE_OAUTH_ENABLED,
        "registration_open": config.REGISTRATION_OPEN,
    }


@router.get("/me")
def me(user=Depends(get_current_user)):
    return user
