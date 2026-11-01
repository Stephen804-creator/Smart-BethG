import secrets

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field, field_validator

import config
from services.auth_service import (
    authenticate_user,
    create_user,
    record_policy_acceptance,
    revoke_user_sessions,
    user_policy_is_current,
    get_user_by_id,
)
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
    accepted_terms: bool = Field(default=False)
    accepted_privacy: bool = Field(default=False)
    age_verified: bool = Field(default=False)

    @field_validator("username")
    @classmethod
    def username_not_blank(cls, v):
        if not v or not v.strip():
            raise ValueError("Username is required.")
        return v.strip()

    @field_validator("accepted_terms", "accepted_privacy", "age_verified")
    @classmethod
    def consent_required(cls, value, info):
        if value is not True:
            field_name = info.field_name.replace("_", " ")
            raise ValueError(f"You must accept the {field_name} requirement to continue.")
        return value


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

    if not user_policy_is_current(user["id"]):
        logger.warning("User %s logged in without current policy acceptance", user["id"])
        # Keep the session restricted while the user reviews the updated 18+ policy.
        request.session.clear()
        request.session["user_id"] = user["id"]
        request.session["session_version"] = user["session_version"]
        csrf = secrets.token_urlsafe(32)
        request.session["csrf_token"] = csrf
        return {"authenticated": False, "policy_update_required": True, "csrf_token": csrf}

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
        revoke_user_sessions(user_id)
    request.session.clear()
    logger.info("User %s logged out; prior sessions revoked", user_id)
    return {"authenticated": False}


@router.post("/register")
def register(payload: RegisterRequest, request: Request, _csrf=Depends(require_csrf)):
    """Create an account only after consent is explicitly recorded for the current legal versions."""
    if not check_rate_limit(f"register:{_client_ip(request)}"):
        logger.warning("Registration rate-limited for %s", _client_ip(request))
        raise HTTPException(status_code=429, detail="Too many attempts. Please wait and try again.")

    try:
        user = create_user(payload.username, payload.password)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    if user is None:
        raise HTTPException(status_code=409, detail="That username is already taken.")

    try:
        record_policy_acceptance(
            user["id"],
            accepted_terms=payload.accepted_terms,
            accepted_privacy=payload.accepted_privacy,
            age_verified=payload.age_verified,
            terms_version=config.TERMS_OF_SERVICE_VERSION,
            privacy_version=config.PRIVACY_POLICY_VERSION,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    logger.info("New user registered: %s", user["id"])
    return {"created": True, "user": user}


class PolicyAcceptanceRequest(BaseModel):
    accepted_terms: bool = Field(default=False)
    accepted_privacy: bool = Field(default=False)
    age_verified: bool = Field(default=False)

    @field_validator("accepted_terms", "accepted_privacy", "age_verified")
    @classmethod
    def consent_required(cls, value, info):
        if value is not True:
            raise ValueError(f"You must confirm {info.field_name.replace('_', ' ')} to continue.")
        return value


@router.post("/accept-policies")
def accept_updated_policies(
    payload: PolicyAcceptanceRequest,
    request: Request,
    _csrf=Depends(require_csrf),
):
    """Record renewed legal acceptance for an authenticated, policy-pending session."""
    user_id = request.session.get("user_id")
    if not user_id:
        raise HTTPException(status_code=401, detail="Sign in before accepting updated policies.")
    user = get_user_by_id(user_id)
    if not user or request.session.get("session_version") != user.get("session_version"):
        request.session.clear()
        raise HTTPException(status_code=401, detail="Your session has expired. Please sign in again.")
    record_policy_acceptance(
        user_id,
        accepted_terms=payload.accepted_terms,
        accepted_privacy=payload.accepted_privacy,
        age_verified=payload.age_verified,
        terms_version=config.TERMS_OF_SERVICE_VERSION,
        privacy_version=config.PRIVACY_POLICY_VERSION,
    )
    logger.info("User %s accepted current 18+ policies", user_id)
    return {"accepted": True}


@router.get("/config")
def auth_config():
    """Lets the frontend know which sign-in options are actually usable."""
    return {
        "google_oauth_enabled": config.GOOGLE_OAUTH_ENABLED,
        "terms_version": config.TERMS_OF_SERVICE_VERSION,
        "privacy_version": config.PRIVACY_POLICY_VERSION,
    }


@router.get("/me")
def me(user=Depends(get_current_user)):
    return user

