from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, field_validator

import config
from services.auth_service import authenticate_user, create_user
from services.rate_limiter import check_rate_limit
from api.dependencies import get_current_user
from logging_setup import get_logger

router = APIRouter(prefix="/auth", tags=["auth"])
logger = get_logger("auth")


class LoginRequest(BaseModel):
    username: str
    password: str


class RegisterRequest(BaseModel):
    username: str
    password: str
    invite_code: str | None = None

    @field_validator("username")
    @classmethod
    def username_not_blank(cls, v):
        if not v or not v.strip():
            raise ValueError("Username is required.")
        return v.strip()


def _client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


@router.post("/login")
def login(payload: LoginRequest, request: Request):
    if not check_rate_limit(f"login:{_client_ip(request)}"):
        logger.warning("Login rate-limited for %s", _client_ip(request))
        raise HTTPException(status_code=429, detail="Too many login attempts. Please wait and try again.")

    user = authenticate_user(payload.username, payload.password)
    if not user:
        logger.info("Failed login attempt for username=%r", payload.username)
        return {"authenticated": False, "error": "Invalid credentials."}
    request.session.clear()
    request.session["user_id"] = user["id"]
    logger.info("User %s logged in", user["id"])
    return {"authenticated": True, "user": user}


@router.post("/logout")
def logout(request: Request):
    user_id = request.session.get("user_id")
    request.session.clear()
    logger.info("User %s logged out", user_id)
    return {"authenticated": False}


@router.post("/register")
def register(payload: RegisterRequest, request: Request):
    """
    Self-registration, gated by two independent operator controls:

    - SMART_BETHG_REGISTRATION_OPEN=false disables this endpoint entirely
      (useful once you've created your own account and don't want anyone
      else signing up).
    - SMART_BETHG_INVITE_CODE, if set, requires the caller to supply the
      same code - a lightweight gate for "friends and family" testing
      without full user management.

    Registration defaults to closed in every environment. An operator must
    explicitly enable it after the public-launch security gates are met.
    """
    if not config.REGISTRATION_OPEN:
        raise HTTPException(status_code=403, detail="Registration is currently closed.")

    if config.REGISTRATION_INVITE_CODE and payload.invite_code != config.REGISTRATION_INVITE_CODE:
        logger.warning("Registration attempt with invalid invite code from %s", _client_ip(request))
        raise HTTPException(status_code=403, detail="A valid invite code is required to register.")

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
    return {"google_oauth_enabled": config.GOOGLE_OAUTH_ENABLED}


@router.get("/me")
def me(user=Depends(get_current_user)):
    return user
