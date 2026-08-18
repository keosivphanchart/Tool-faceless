import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from app.api.router import api_router
from app.config import settings
from app.db import init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


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
