"""Module 8 orchestrator: weekly job that pulls performance for every
published video, stores it linked to its source topic/script style, and
surfaces "what's working" aggregates for the dashboard / script generator.

Usage:
    python -m app.modules.analytics.run
"""
import logging

from sqlalchemy.orm import Session

from app.db import SessionLocal, init_db
from app.models import Performance, Video, VideoStatus
from app.modules.analytics.tiktok_analytics import TikTokNotConfigured
from app.modules.analytics.tiktok_analytics import fetch_video_performance as fetch_tiktok
from app.modules.analytics.youtube_analytics import fetch_video_performance as fetch_youtube

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def pull_all_performance(db: Session) -> int:
    published = db.query(Video).filter(Video.status == VideoStatus.published).all()
    pulled = 0

    for video in published:
        platform_ids = video.platform_ids or {}

        if "youtube" in platform_ids:
            try:
                stats = fetch_youtube(platform_ids["youtube"])
                db.add(Performance(video_id=video.id, platform="youtube", **stats))
                pulled += 1
            except Exception:
                logger.exception("YouTube analytics pull failed for video %s", video.id)

        if "tiktok" in platform_ids:
            try:
                stats = fetch_tiktok(platform_ids["tiktok"])
                db.add(Performance(video_id=video.id, platform="tiktok", **stats))
                pulled += 1
            except TikTokNotConfigured:
                pass
            except Exception:
                logger.exception("TikTok analytics pull failed for video %s", video.id)

    db.commit()
    return pulled


def best_performing_patterns(db: Session, top_n: int = 5) -> dict:
    """Surfaces the best-performing hook style / topic category, by
    average views across the most recent performance pull per video."""
    import pandas as pd

    rows = (
        db.query(Performance, Video)
        .join(Video, Performance.video_id == Video.id)
        .all()
    )
    if not rows:
        return {"by_style": [], "by_topic": []}

    records = [
        {
            "style": video.script.style,
            "topic": video.script.topic,
            "views": perf.views,
            "retention_pct": perf.retention_pct,
        }
        for perf, video in rows
    ]
    df = pd.DataFrame(records)

    by_style = (
        df.groupby("style")[["views", "retention_pct"]]
        .mean()
        .sort_values("views", ascending=False)
        .head(top_n)
        .reset_index()
        .to_dict(orient="records")
    )
    by_topic = (
        df.groupby("topic")[["views", "retention_pct"]]
        .mean()
        .sort_values("views", ascending=False)
        .head(top_n)
        .reset_index()
        .to_dict(orient="records")
    )
    return {"by_style": by_style, "by_topic": by_topic}


if __name__ == "__main__":
    init_db()
    session = SessionLocal()
    try:
        count = pull_all_performance(session)
        print(f"Pulled {count} performance records")
    finally:
        session.close()
