"""Dashboard login: a single admin password (DASHBOARD_PASSWORD) gating
the API behind a session cookie, checked by main.py's auth middleware.
Empty DASHBOARD_PASSWORD (the default) means auth is off entirely - see
that middleware for the enforcement side of this.
"""
import secrets

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from faceless_pipeline.config import settings

router = APIRouter()


class LoginRequest(BaseModel):
    password: str


@router.get("/status")
def auth_status(request: Request):
    enabled = bool(settings.dashboard_password)
    return {"enabled": enabled, "authenticated": (not enabled) or bool(request.session.get("authenticated"))}


@router.post("/login")
def login(payload: LoginRequest, request: Request):
    if not settings.dashboard_password:
        return {"authenticated": True}
    # constant-time compare - a password check is exactly the kind of
    # comparison a timing attack targets.
    if not secrets.compare_digest(payload.password, settings.dashboard_password):
        raise HTTPException(status_code=401, detail="Invalid password")
    request.session["authenticated"] = True
    return {"authenticated": True}


@router.post("/logout")
def logout(request: Request):
    request.session.clear()
    return {"authenticated": False}
