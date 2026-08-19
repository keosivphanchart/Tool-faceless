"""Stale data cleanup — rejected/superseded scripts and videos (and
their rendered media files on disk) accumulate forever otherwise. Off by
default (CLEANUP_ENABLED); only ever touches rows already in a terminal,
non-actionable state past CLEANUP_RETENTION_DAYS old, never anything
pending/approved/published.
"""
import asyncio
import logging
from datetime import datetime, timedelta
from pathlib import Path

from sqlalchemy.orm import Session

from faceless_pipeline.config import settings

logger = logging.getLogger(__name__)

_MEDIA_FIELDS = ("file_path", "thumbnail_path", "audio_path", "captions_path", "metadata_path")


def _delete_video_files(video) -> None:
    for field in _MEDIA_FIELDS:
        path = getattr(video, field, None)
        if not path:
            continue
        try:
            Path(path).unlink(missing_ok=True)
        except OSError:
            logger.warning("Could not delete %s for video %s", path, video.id)


def cleanup_stale_data(db: Session, retention_days: int | None = None) -> dict:
    """Deletes Video rows with status='rejected' (and their files) and
    Script rows with status='superseded', both older than the retention
    window. A rejected Video's parent Script is left alone unless the
    script itself has no other videos and is also past its own status
    check - kept deliberately conservative (delete videos freely, only
    delete scripts that are explicitly superseded) rather than inferring
    "orphaned" scripts, since a script can be legitimately kept around
    for its history/audit trail even with no surviving video.
    """
    from faceless_pipeline.models import Script, Video, VideoStatus

    retention_days = retention_days if retention_days is not None else settings.cleanup_retention_days
    cutoff = datetime.utcnow() - timedelta(days=retention_days)

    stale_videos = (
        db.query(Video).filter(Video.status == VideoStatus.rejected, Video.created_at < cutoff).all()
    )
    for video in stale_videos:
        _delete_video_files(video)
        db.delete(video)

    # ~Script.videos.any(): only a script with zero remaining Video rows
    # (already cleaned up above, or never had one) - Video.script_id is a
    # NOT NULL foreign key and SQLite doesn't enforce FK constraints in
    # this project, so deleting a script a video still points at would
    # silently leave a dangling reference instead of erroring.
    stale_scripts = (
        db.query(Script)
        .filter(Script.status == "superseded", Script.created_at < cutoff, ~Script.videos.any())
        .all()
    )
    for script in stale_scripts:
        db.delete(script)

    db.commit()
    return {"videos_deleted": len(stale_videos), "scripts_deleted": len(stale_scripts)}


async def run_cleanup_loop() -> None:
    from faceless_pipeline.api.pipeline import record_run
    from faceless_pipeline.db import SessionLocal

    interval_seconds = max(settings.cleanup_interval_hours, 1) * 3600

    def _tick():
        db = SessionLocal()
        try:
            result = cleanup_stale_data(db)
            if result["videos_deleted"] or result["scripts_deleted"]:
                record_run(
                    "cleanup",
                    "success",
                    f"deleted {result['videos_deleted']} rejected video(s), {result['scripts_deleted']} superseded script(s)",
                )
        finally:
            db.close()

    while True:
        await asyncio.sleep(interval_seconds)
        try:
            await asyncio.to_thread(_tick)
        except Exception:
            logger.exception("Cleanup loop tick failed")
