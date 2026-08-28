import asyncio
import logging
import os
import secrets
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from starlette.middleware.sessions import SessionMiddleware

from faceless_pipeline.api.router import api_router
from faceless_pipeline.config import settings
from faceless_pipeline.db import init_db
from faceless_pipeline.modules.automation.cleanup import run_cleanup_loop
from faceless_pipeline.modules.automation.digest import run_digest_loop
from faceless_pipeline.modules.automation.health import run_health_check_loop
from faceless_pipeline.modules.automation.scheduler import run_recurring_automation_loop
from faceless_pipeline.modules.publisher.recurring import run_recurring_posting_loop
from faceless_pipeline.modules.publisher.scheduler import run_scheduler_loop

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    if not settings.dashboard_password:
        logger.warning(
            "DASHBOARD_PASSWORD is not set - every API endpoint is unauthenticated. Fine for local "
            "dev, never for anything reachable beyond localhost."
        )

    # publisher.scheduler's loop (dispatching per-video scheduled
    # publishes) and publisher.recurring's loop (dispatching recurring
    # posting slots) always run - both are the execution side of a
    # feature that's always available, not itself opt-in (an empty slot
    # list just makes recurring's loop a no-op tick). Everything else
    # here is genuinely opt-in automation, off unless its setting says
    # otherwise.
    tasks = [asyncio.create_task(run_scheduler_loop()), asyncio.create_task(run_recurring_posting_loop())]
    if settings.auto_trend_finder_enabled:
        tasks.append(asyncio.create_task(run_recurring_automation_loop()))
    tasks.append(asyncio.create_task(run_health_check_loop()))  # read-only, no cost - always safe to run
    if settings.digest_enabled:
        tasks.append(asyncio.create_task(run_digest_loop()))
    if settings.cleanup_enabled:
        tasks.append(asyncio.create_task(run_cleanup_loop()))

    yield

    for task in tasks:
        task.cancel()


app = FastAPI(title="Faceless Content Pipeline", version="0.1.0", lifespan=lifespan)

# Paths reachable without a session - the login/status checks themselves,
# obviously, since a client can't be authenticated before it's had a
# chance to log in or check whether it needs to.
_AUTH_EXEMPT_PATHS = {"/health", "/api/auth/login", "/api/auth/status"}


@app.middleware("http")
async def require_dashboard_auth(request: Request, call_next):
    """Gates every /api/* request behind the dashboard session cookie
    once DASHBOARD_PASSWORD is set (empty = auth off, unchanged from
    before this existed). Deliberately does NOT cover /media: that
    endpoint is also fetched server-side by Meta's servers (no cookie
    available) when publishing an Instagram Reel, so gating it would
    silently break Instagram publishing - see instagram.py's
    _video_url(). It's already restricted to OUTPUT_DIR, not an open
    filesystem read.
    """
    if not settings.dashboard_password or request.method == "OPTIONS" or request.url.path in _AUTH_EXEMPT_PATHS:
        return await call_next(request)
    if not request.url.path.startswith("/api/"):
        return await call_next(request)
    if not request.session.get("authenticated"):
        return JSONResponse({"detail": "Not authenticated"}, status_code=401)
    return await call_next(request)


# Registration order matters: Starlette applies the *last*-added
# middleware outermost (runs first per request), so this order gives
# CORS -> session -> auth-check -> routes. Session has to run before the
# auth check reads request.session; CORS has to wrap everything so even
# a 401 from the auth check still carries CORS headers.
app.add_middleware(
    SessionMiddleware,
    secret_key=settings.dashboard_session_secret or secrets.token_hex(32),
    same_site="lax",
    max_age=60 * 60 * 24 * 7,  # 7 days
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/media")
def media(path: str):
    """Serves rendered video/thumbnail/audio files for the review UI.
    Restricted to OUTPUT_DIR to prevent path traversal.
    """
    output_root = os.path.realpath(settings.output_dir)
    requested = os.path.realpath(path)
    if os.path.commonpath([output_root, requested]) != output_root:
        raise HTTPException(status_code=403, detail="Path outside of OUTPUT_DIR")
    if not os.path.isfile(requested):
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(requested)


app.include_router(api_router)
