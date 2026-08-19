"""Recurring pipeline automation: runs the trend finder (and, if enabled,
auto-generation) on a fixed interval instead of requiring a human or an
external cron to click "Run trend finder now". Off by default
(AUTO_TREND_FINDER_ENABLED) — only started from main.py's lifespan when
explicitly turned on.
"""
import asyncio
import logging

from faceless_pipeline.config import settings

logger = logging.getLogger(__name__)


def run_recurring_cycle() -> None:
    """One tick: find trends, then auto-generate from them if that's
    also enabled. Synchronous - the caller runs it off the event loop
    via asyncio.to_thread, same reasoning as publisher/scheduler.py
    (network/ffmpeg calls inside would otherwise block every other
    request while a tick is in progress)."""
    from faceless_pipeline.api.pipeline import record_run
    from faceless_pipeline.db import SessionLocal
    from faceless_pipeline.modules.automation.run import auto_generate_from_trends
    from faceless_pipeline.modules.trends.run import run_trend_finder

    try:
        trends = run_trend_finder()
        record_run("trends", "success", f"{len(trends)} new topics (recurring automation)")
    except Exception as exc:
        record_run("trends", "error", f"recurring automation: {exc}")
        logger.exception("Recurring trend finder tick failed")
        return

    if not settings.auto_generate_enabled:
        return

    db = SessionLocal()
    try:
        generated = auto_generate_from_trends(db)
        if generated:
            topics = ", ".join(s.topic for s in generated)
            record_run("script", "success", f"auto-generated {len(generated)} (recurring automation): {topics}")
    except Exception as exc:
        record_run("script", "error", f"recurring auto-generate: {exc}")
        logger.exception("Recurring auto-generate tick failed")
    finally:
        db.close()


async def run_recurring_automation_loop() -> None:
    interval_seconds = max(settings.auto_trend_finder_interval_hours, 1) * 3600
    while True:
        # Sleep first, not run-then-sleep: a server restart (deploy, crash
        # recovery) shouldn't itself trigger a fresh cycle - especially
        # with AUTO_GENERATE_ENABLED on, where that cycle spends real LLM
        # API calls. Worst case a slow-to-restart deployment delays one
        # cycle by up to the interval, which is the safer failure mode.
        await asyncio.sleep(interval_seconds)
        try:
            await asyncio.to_thread(run_recurring_cycle)
        except Exception:
            logger.exception("Recurring automation loop tick failed")
