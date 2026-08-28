"""Periodic Telegram/Discord digest — a rollup of what happened over the
last DIGEST_INTERVAL_HOURS (trends found, scripts generated, videos
published, top performer), instead of only ever getting a per-video
"ready for review" ping. Off by default (DIGEST_ENABLED).
"""
import asyncio
import logging
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from faceless_pipeline.config import settings

logger = logging.getLogger(__name__)


def build_digest_message(db: Session) -> str:
    from faceless_pipeline.models import Script, Trend, Video, VideoStatus
    from faceless_pipeline.modules.analytics.run import best_performing_patterns

    since = datetime.utcnow() - timedelta(hours=settings.digest_interval_hours)

    trends_found = db.query(Trend).filter(Trend.created_at >= since).count()
    scripts_generated = db.query(Script).filter(Script.created_at >= since).count()
    videos_published = (
        db.query(Video).filter(Video.status == VideoStatus.published, Video.created_at >= since).count()
    )

    lines = [
        f"Faceless Pipeline digest (last {settings.digest_interval_hours}h)",
        f"- {trends_found} new trend{'s' if trends_found != 1 else ''} found",
        f"- {scripts_generated} script{'s' if scripts_generated != 1 else ''} generated",
        f"- {videos_published} video{'s' if videos_published != 1 else ''} published",
    ]

    top_topics = best_performing_patterns(db)["by_topic"]
    if top_topics:
        top = top_topics[0]
        lines.append(f"- Top performer: '{top['topic']}' ({top['views']:.0f} avg views)")

    return "\n".join(lines)


def send_digest() -> None:
    from faceless_pipeline.db import SessionLocal
    from faceless_pipeline.modules.review.notify import send_notification

    db = SessionLocal()
    try:
        message = build_digest_message(db)
    finally:
        db.close()

    send_notification(message)


CHECK_INTERVAL_SECONDS = 60


def digest_due(last_sent: datetime, now: datetime) -> bool:
    """Reads settings.digest_enabled/digest_interval_hours fresh on every
    call (not captured once at loop start), which is what makes both
    settable live from the dashboard without a restart."""
    if not settings.digest_enabled:
        return False
    interval = timedelta(hours=max(settings.digest_interval_hours, 1))
    return now - last_sent >= interval


async def run_digest_loop() -> None:
    """Always runs (like publisher/scheduler.py's dispatcher) so flipping
    DIGEST_ENABLED from the dashboard takes effect without a restart,
    instead of only being checked once at process startup to decide
    whether to spawn this loop at all. Polls every minute rather than
    sleeping a full DIGEST_INTERVAL_HOURS so a changed interval is also
    picked up live. last_sent starts at "now" (not unset) to preserve
    the original sleep-first behavior: a restart doesn't itself trigger
    a fresh digest, even with DIGEST_ENABLED already on.
    """
    last_sent = datetime.utcnow()
    while True:
        await asyncio.sleep(CHECK_INTERVAL_SECONDS)
        if not digest_due(last_sent, datetime.utcnow()):
            continue
        last_sent = datetime.utcnow()
        try:
            await asyncio.to_thread(send_digest)
        except Exception:
            logger.exception("Digest loop tick failed")
