"""Orchestrates Module 1: pull from all trend sources, dedupe, persist
new topics, skip anything already seen. Designed to be the target of a
daily cron job / n8n schedule, or triggered manually from the dashboard.

Usage:
    python -m faceless_pipeline.modules.trends.run
"""
import logging
from concurrent.futures import ThreadPoolExecutor

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


def _fetch_all_sources() -> list[dict]:
    """Each source is an independent, blocking network call (google
    trends / youtube / reddit / tiktok / news APIs). Run sequentially,
    the total wait is the *sum* of all five — one slow or timed-out
    source (each has its own timeout up to 30s) delays every source
    behind it. Each function already catches its own exceptions
    internally and returns [] on failure, so running them concurrently
    doesn't change error handling, just how long a caller waits for the
    slowest one instead of all of them added together.

    The fetcher list is built here, not at module import time — building
    it once at import time would bind directly to the original function
    objects, which breaks the standard `patch.object(module, name)` /
    `monkeypatch.setattr(module, name, ...)` pattern this test suite uses
    everywhere: patching the module attribute afterward wouldn't reach a
    reference already captured in an import-time list.
    """
    fetchers = [
        lambda: fetch_google_trends(settings.trend_seed_keyword_list),
        fetch_youtube_trending,
        fetch_reddit_trends,
        fetch_tiktok_trends,
        fetch_news_trends,
    ]

    candidates: list[dict] = []
    with ThreadPoolExecutor(max_workers=len(fetchers)) as pool:
        futures = [pool.submit(fetcher) for fetcher in fetchers]
        for future in futures:
            try:
                candidates += future.result()
            except Exception:
                logger.exception("A trend source raised unexpectedly (should be self-contained)")
    return candidates


def run_trend_finder() -> list[Trend]:
    db = SessionLocal()
    try:
        candidates = _fetch_all_sources()

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
