"""Background dispatcher for recurring posting slots.

The existing scheduler (scheduler.py) handles "publish this one video at
this one datetime". This handles the other shape of scheduling: "publish
something every Mon/Wed/Fri at 18:00 UTC" without picking a video by hand
each time - each PostingSlot just fires at its configured day/time and
grabs whichever approved video has been waiting longest.
"""
import asyncio
import logging
from datetime import datetime

from sqlalchemy.orm import Session

from faceless_pipeline.db import SessionLocal
from faceless_pipeline.models import PostingSlot, Video, VideoStatus

logger = logging.getLogger(__name__)

CHECK_INTERVAL_SECONDS = 60


def _due_slots(db: Session, now: datetime) -> list[PostingSlot]:
    today = now.date().isoformat()
    current_hhmm = now.strftime("%H:%M")
    weekday = now.weekday()  # Monday=0 .. Sunday=6

    return [
        slot
        for slot in db.query(PostingSlot).filter(PostingSlot.enabled.is_(True)).all()
        if weekday in (slot.days_of_week or [])
        and current_hhmm >= slot.time_of_day
        and slot.last_fired_date != today
    ]


def _next_queued_video(db: Session) -> Video | None:
    """The oldest approved video that isn't already individually
    scheduled - recurring slots draw from this queue instead of stealing
    a video someone deliberately scheduled for a specific time."""
    return (
        db.query(Video)
        .filter(Video.status == VideoStatus.approved, Video.scheduled_for.is_(None))
        .order_by(Video.created_at.asc())
        .first()
    )


def dispatch_due_posting_slots() -> int:
    """Fires every recurring slot whose day/time has arrived today and
    hasn't already fired today. A slot that finds no approved video ready
    is marked fired anyway (rather than retried every tick for the rest
    of the day) - same "just note it and move on" behavior as the
    quota/network failure path below. Returns the number of slots fired.
    """
    from faceless_pipeline.api.pipeline import record_run
    from faceless_pipeline.modules.publisher.run import publish_video

    db = SessionLocal()
    fired = 0
    try:
        now = datetime.utcnow()
        today = now.date().isoformat()
        for slot in _due_slots(db, now):
            fired += 1
            name = slot.label or slot.time_of_day
            video = _next_queued_video(db)

            if video is None:
                record_run("publish", "success", f"recurring slot '{name}': no approved video ready")
            else:
                try:
                    published = publish_video(db, video.id, platforms=slot.platforms)
                    if published.platform_ids:
                        platforms = ", ".join(str(p) for p in published.platform_ids)
                        record_run("publish", "success", f"recurring slot '{name}' published video {video.id} -> {platforms}")
                    else:
                        record_run("publish", "error", f"recurring slot '{name}': video {video.id}, no platform accepted the upload")
                except Exception as exc:
                    record_run("publish", "error", f"recurring slot '{name}': video {video.id} failed: {exc}")
                    logger.exception("Recurring slot publish failed for video %s", video.id)

            slot.last_fired_date = today
            db.commit()
        return fired
    finally:
        db.close()


async def run_recurring_posting_loop() -> None:
    while True:
        try:
            await asyncio.to_thread(dispatch_due_posting_slots)
        except Exception:
            logger.exception("Recurring posting-slot dispatch tick failed")
        await asyncio.sleep(CHECK_INTERVAL_SECONDS)
