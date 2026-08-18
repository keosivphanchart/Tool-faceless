"""Background dispatcher for scheduled publishes.

publish_video() with a `scheduled_for` in the future just stores that
timestamp on the video and returns — approving a video with a schedule
used to be a dead end, since nothing ever came back to actually publish
it once that time arrived. This loop runs inside the FastAPI process
(started from main.py's lifespan) and periodically checks for approved
videos whose scheduled_for has passed, and publishes them for real.
"""
import asyncio
import logging
from datetime import datetime

from faceless_pipeline.db import SessionLocal
from faceless_pipeline.models import Video, VideoStatus

logger = logging.getLogger(__name__)

CHECK_INTERVAL_SECONDS = 60


def dispatch_due_scheduled_publishes() -> int:
    """Publishes every approved video whose scheduled_for has passed.
    Returns the number of videos it attempted. A video that fails to
    publish (quota, network, no platform configured) stays approved with
    scheduled_for still in the past, so the next tick retries it
    automatically — same as the existing "leave video approved and retry
    later" behavior for quota-exceeded errors.
    """
    from faceless_pipeline.api.pipeline import record_run
    from faceless_pipeline.modules.publisher.run import publish_video

    db = SessionLocal()
    attempted = 0
    try:
        due = (
            db.query(Video)
            .filter(
                Video.status == VideoStatus.approved,
                Video.scheduled_for.isnot(None),
                Video.scheduled_for <= datetime.utcnow(),
            )
            .all()
        )
        for video in due:
            attempted += 1
            try:
                # No scheduled_for passed here — that's what routes
                # publish_video() into its immediate-publish branch
                # instead of the "just store it" branch this video
                # already went through once, at approval time.
                published = publish_video(db, video.id)
                if published.platform_ids:
                    platforms = ", ".join(str(p) for p in published.platform_ids)
                    record_run("publish", "success", f"video {video.id} published on schedule -> {platforms}")
                else:
                    record_run(
                        "publish", "error", f"video {video.id}: scheduled publish, no platform accepted the upload"
                    )
            except Exception as exc:
                record_run("publish", "error", f"video {video.id}: scheduled publish failed: {exc}")
                logger.exception("Scheduled publish failed for video %s", video.id)
        return attempted
    finally:
        db.close()


async def run_scheduler_loop() -> None:
    while True:
        try:
            await asyncio.to_thread(dispatch_due_scheduled_publishes)
        except Exception:
            logger.exception("Scheduled-publish dispatch tick failed")
        await asyncio.sleep(CHECK_INTERVAL_SECONDS)
