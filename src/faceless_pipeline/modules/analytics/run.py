"""Module 8 orchestrator: weekly job that pulls performance for every
published video, stores it linked to its source topic/script style, and
surfaces "what's working" aggregates for the dashboard / script generator.

Usage:
    python -m faceless_pipeline.modules.analytics.run
"""
import logging

from sqlalchemy.orm import Session, joinedload

from faceless_pipeline.db import SessionLocal, init_db
from faceless_pipeline.models import Performance, Video, VideoStatus
from faceless_pipeline.modules.analytics.tiktok_analytics import TikTokNotConfigured
from faceless_pipeline.modules.analytics.tiktok_analytics import fetch_video_performance as fetch_tiktok
from faceless_pipeline.modules.analytics.youtube_analytics import fetch_video_performance as fetch_youtube

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
    average views across the most recent performance pull per video.

    Must restrict to one row per (video, platform), not every row ever
    pulled: pull_all_performance() is a *weekly* job that inserts a new
    Performance row per video per platform on every run rather than
    updating one in place, so a long-lived video accumulates many rows
    over time. Averaging across all of them (as this used to do) let a
    video's own pull *count* dominate the style/topic average it belongs
    to - a video pulled every week for 20 weeks outweighs 20 different
    videos each pulled once, even if the 20-week video is a mediocre
    performer, which is exactly backwards for a "what's working" signal
    meant to feed back into future script generation.
    """
    import pandas as pd
    from sqlalchemy import func

    latest_per_video_platform = (
        db.query(
            Performance.video_id,
            Performance.platform,
            func.max(Performance.pulled_at).label("max_pulled_at"),
        )
        .group_by(Performance.video_id, Performance.platform)
        .subquery()
    )

    # joinedload(Video.script) avoids an N+1: without it, the .style/.topic
    # access in the list comprehension below fires one extra SELECT per
    # performance row.
    rows = (
        db.query(Performance, Video)
        .join(Video, Performance.video_id == Video.id)
        .join(
            latest_per_video_platform,
            (Performance.video_id == latest_per_video_platform.c.video_id)
            & (Performance.platform == latest_per_video_platform.c.platform)
            & (Performance.pulled_at == latest_per_video_platform.c.max_pulled_at),
        )
        .options(joinedload(Video.script))
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


def best_posting_times(db: Session, top_n: int = 5) -> dict:
    """Suggests, per platform, which hour of day (UTC) has historically
    drawn the most average views - so a recurring posting slot can be set
    at an informed time instead of a guess. Same latest-per-(video,
    platform) dedup as best_performing_patterns(), keyed off
    Video.published_at (the actual publish timestamp, not scheduled_for
    which is only set for videos that were scheduled ahead of time)."""
    import pandas as pd
    from sqlalchemy import func

    latest_per_video_platform = (
        db.query(
            Performance.video_id,
            Performance.platform,
            func.max(Performance.pulled_at).label("max_pulled_at"),
        )
        .group_by(Performance.video_id, Performance.platform)
        .subquery()
    )

    rows = (
        db.query(Performance, Video)
        .join(Video, Performance.video_id == Video.id)
        .join(
            latest_per_video_platform,
            (Performance.video_id == latest_per_video_platform.c.video_id)
            & (Performance.platform == latest_per_video_platform.c.platform)
            & (Performance.pulled_at == latest_per_video_platform.c.max_pulled_at),
        )
        .filter(Video.published_at.isnot(None))
        .all()
    )
    if not rows:
        return {}

    records = [{"platform": perf.platform, "hour": video.published_at.hour, "views": perf.views} for perf, video in rows]
    df = pd.DataFrame(records)

    result = {}
    for platform, group in df.groupby("platform"):
        agg = (
            group.groupby("hour")["views"]
            .agg(avg_views="mean", sample_count="count")
            .sort_values("avg_views", ascending=False)
            .head(top_n)
            .reset_index()
        )
        result[platform] = [
            {"hour": int(r["hour"]), "avg_views": round(float(r["avg_views"]), 1), "sample_count": int(r["sample_count"])}
            for r in agg.to_dict(orient="records")
        ]
    return result


if __name__ == "__main__":
    init_db()
    session = SessionLocal()
    try:
        count = pull_all_performance(session)
        print(f"Pulled {count} performance records")
    finally:
        session.close()
