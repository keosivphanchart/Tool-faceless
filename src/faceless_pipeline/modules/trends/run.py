"""Orchestrates Module 1: pull from all trend sources, dedupe, persist
new topics, skip anything already seen. Designed to be the target of a
daily cron job / n8n schedule, or triggered manually from the dashboard.

Usage:
    python -m faceless_pipeline.modules.trends.run
"""
import logging

from sqlalchemy.orm import Session

from faceless_pipeline.config import settings
from faceless_pipeline.db import SessionLocal, init_db
from faceless_pipeline.models import Trend
from faceless_pipeline.modules.trends.dedup import dedupe_topics, normalize_topic
from faceless_pipeline.modules.trends.google_trends import fetch_google_trends
from faceless_pipeline.modules.trends.news_trends import fetch_news_trends
from faceless_pipeline.modules.trends.reddit_trends import fetch_reddit_trends
from faceless_pipeline.modules.trends.tiktok_trends import fetch_tiktok_trends
from faceless_pipeline.modules.trends.youtube_trending import fetch_youtube_trending

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def _existing_normalized_topics(db: Session) -> set[str]:
    return {row[0] for row in db.query(Trend.normalized_topic).all()}


def run_trend_finder() -> list[Trend]:
    db = SessionLocal()
    try:
        candidates: list[dict] = []
        candidates += fetch_google_trends(settings.trend_seed_keyword_list)
        candidates += fetch_youtube_trending()
        candidates += fetch_reddit_trends()
        candidates += fetch_tiktok_trends()
        candidates += fetch_news_trends()

        logger.info("Collected %d raw candidates from all sources", len(candidates))

        existing = _existing_normalized_topics(db)
        deduped = dedupe_topics(candidates, existing_normalized=existing)
        logger.info("%d topics remain after deduplication / history check", len(deduped))

        saved: list[Trend] = []
        for item in deduped:
            trend = Trend(
                topic=item["topic"],
                normalized_topic=item.get("normalized_topic") or normalize_topic(item["topic"]),
                source=item["source"],
                score=item["score"],
            )
            db.add(trend)
            saved.append(trend)

        db.commit()
        for trend in saved:
            db.refresh(trend)

        logger.info("Persisted %d new trends", len(saved))
        return saved
    finally:
        db.close()


if __name__ == "__main__":
    init_db()
    run_trend_finder()
