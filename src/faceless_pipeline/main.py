import asyncio
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from faceless_pipeline.api.router import api_router
from faceless_pipeline.config import settings
from faceless_pipeline.db import init_db
from faceless_pipeline.modules.automation.cleanup import run_cleanup_loop
from faceless_pipeline.modules.automation.digest import run_digest_loop
from faceless_pipeline.modules.automation.health import run_health_check_loop
from faceless_pipeline.modules.automation.scheduler import run_recurring_automation_loop
from faceless_pipeline.modules.publisher.recurring import run_recurring_posting_loop
from faceless_pipeline.modules.publisher.scheduler import run_scheduler_loop


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()

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
