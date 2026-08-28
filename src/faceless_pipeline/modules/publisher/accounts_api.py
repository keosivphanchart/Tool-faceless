"""Dashboard-driven connect/disconnect for the publish-account credentials
(YouTube upload, TikTok video.publish). Lets a first-time setup authorize
an account by clicking a button in the Settings page instead of running a
script by hand — the OAuth app credentials (client key/secret) still have
to be set in .env first, this only replaces the interactive consent step.
"""
import logging

from fastapi import APIRouter, HTTPException
from fastapi.responses import RedirectResponse

from faceless_pipeline.config import settings
from faceless_pipeline.modules.publisher import tiktok, youtube

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/status")
def accounts_status():
    return {
        "youtube": {
            "configured": youtube._client_secrets_path().exists(),
            "connected": youtube.is_connected(),
        },
        "tiktok": {
            "configured": bool(settings.tiktok_client_key and settings.tiktok_client_secret),
            "connected": tiktok.is_connected(),
        },
    }


@router.get("/youtube/connect")
def youtube_connect():
    try:
        return RedirectResponse(youtube.build_authorize_url())
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.get("/youtube/callback")
def youtube_callback(code: str | None = None, error: str | None = None):
    if error:
        return RedirectResponse(f"{settings.dashboard_url}/settings?error=youtube_{error}")
    try:
        youtube.complete_authorization(code)
    except Exception:
        logger.exception("YouTube OAuth callback failed")
        return RedirectResponse(f"{settings.dashboard_url}/settings?error=youtube_authorization_failed")
    return RedirectResponse(f"{settings.dashboard_url}/settings?connected=youtube")


@router.post("/youtube/disconnect")
def youtube_disconnect():
    youtube.disconnect()
    return {"connected": False}


@router.get("/tiktok/connect")
def tiktok_connect():
    try:
        return RedirectResponse(tiktok.build_authorize_url())
    except tiktok.TikTokNotConfigured as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.get("/tiktok/callback")
def tiktok_callback(code: str | None = None, error: str | None = None):
    if error:
        return RedirectResponse(f"{settings.dashboard_url}/settings?error=tiktok_{error}")
    try:
        tiktok.complete_authorization(code)
    except Exception:
        logger.exception("TikTok OAuth callback failed")
        return RedirectResponse(f"{settings.dashboard_url}/settings?error=tiktok_authorization_failed")
    return RedirectResponse(f"{settings.dashboard_url}/settings?connected=tiktok")


@router.post("/tiktok/disconnect")
def tiktok_disconnect():
    tiktok.disconnect()
    return {"connected": False}
