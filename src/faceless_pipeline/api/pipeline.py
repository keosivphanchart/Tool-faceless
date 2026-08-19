"""Pipeline status + manual trigger endpoints (backs the Module 7 dashboard's
'last run time/status per stage' view and 'run trend finder now' style buttons).
"""
from collections import deque
from datetime import datetime

from fastapi import APIRouter, BackgroundTasks

router = APIRouter()

# In-memory run log for MVP. Swap for a `pipeline_runs` table if this needs
# to survive restarts or be queried historically.
_last_runs: dict[str, dict] = {}

# A bounded event log (distinct from _last_runs, which only keeps the
# *latest* run per stage name and so clobbers itself when the same stage
# fires for different videos — e.g. two publish failures for different
# video_ids would otherwise overwrite each other and the dashboard would
# only ever see the second one). Background jobs (publish, regenerate)
# used to just log exceptions server-side with no dashboard-visible
# trace at all; every record_run() call now also appends here so the
# dashboard can poll for events it hasn't shown yet and surface failures
# as they happen instead of requiring someone to know to check this page.
_MAX_EVENTS = 200
_events: deque[dict] = deque(maxlen=_MAX_EVENTS)
_next_event_id = 1


def record_run(stage: str, status: str, detail: str = ""):
    global _next_event_id

    entry = {
        "stage": stage,
        "status": status,
        "detail": detail,
        "at": datetime.utcnow().isoformat(),
    }
    _last_runs[stage] = entry
    _events.append({"id": _next_event_id, **entry})
    _next_event_id += 1


@router.get("/status")
def pipeline_status():
    return {"stages": list(_last_runs.values())}


@router.get("/events")
def pipeline_events(after: int = 0):
    """Polled by the dashboard's global failure toast. Returns every
    event with id > `after` so the client only has to remember the
    highest id it's already seen, not a timestamp or full history."""
    return {"events": [e for e in _events if e["id"] > after]}


@router.post("/trigger/trends")
def trigger_trend_finder(background_tasks: BackgroundTasks):
    from faceless_pipeline.config import settings
    from faceless_pipeline.modules.trends.run import run_trend_finder

    def _job():
        try:
            trends = run_trend_finder()
            record_run("trends", "success", f"{len(trends)} new topics")
        except Exception as exc:  # surfaced in the dashboard's status view
            record_run("trends", "error", str(exc))
            return

        # AUTO_GENERATE_ENABLED: closes trend -> script -> video with no
        # human topic pick, for whoever wants that instead of always
        # choosing manually from the Trends page.
        if settings.auto_generate_enabled:
            _auto_generate_job()

    background_tasks.add_task(_job)
    return {"triggered": "trends"}


def _auto_generate_job():
    from faceless_pipeline.db import SessionLocal
    from faceless_pipeline.modules.automation.run import auto_generate_from_trends

    db = SessionLocal()
    try:
        generated = auto_generate_from_trends(db)
        if generated:
            topics = ", ".join(s.topic for s in generated)
            record_run("script", "success", f"auto-generated {len(generated)}: {topics}")
    except Exception as exc:
        record_run("script", "error", f"auto-generate: {exc}")
    finally:
        db.close()


@router.post("/trigger/full-cycle")
def trigger_full_cycle(count: int | None = None, min_score: float | None = None, background_tasks: BackgroundTasks = None):
    """One call that runs trend finder and then generates+assembles
    videos for the top new trends, meant for an external cron/n8n/Zapier
    hook that wants "do everything" instead of orchestrating trend-finder
    and script-generation as two separate calls itself. Unlike
    AUTO_GENERATE_ENABLED (which makes *every* trend-finder run also
    auto-generate), this is a deliberate one-shot regardless of that
    setting — count/min_score override the AUTO_GENERATE_* defaults for
    just this call.
    """
    from faceless_pipeline.db import SessionLocal
    from faceless_pipeline.modules.automation.run import auto_generate_from_trends
    from faceless_pipeline.modules.trends.run import run_trend_finder

    def _job():
        try:
            trends = run_trend_finder()
            record_run("trends", "success", f"{len(trends)} new topics (full-cycle)")
        except Exception as exc:
            record_run("trends", "error", f"full-cycle: {exc}")
            return

        db = SessionLocal()
        try:
            generated = auto_generate_from_trends(db, count=count, min_score=min_score)
            if generated:
                topics = ", ".join(s.topic for s in generated)
                record_run("script", "success", f"full-cycle generated {len(generated)}: {topics}")
        except Exception as exc:
            record_run("script", "error", f"full-cycle auto-generate: {exc}")
        finally:
            db.close()

    if background_tasks is not None:
        background_tasks.add_task(_job)
    else:
        _job()
    return {"triggered": "full-cycle"}


@router.post("/trigger/script")
def trigger_script_generation(topic: str, style: str = "explainer", length_variant: str = "30s", background_tasks: BackgroundTasks = None):
    """Generates a script AND assembles the video for it, so a script
    never just sits there — per the spec, voice/video assembly happens
    automatically once a script exists, not as a separate manual step a
    human has to remember to trigger. Trend -> script stays a deliberate
    choice (this endpoint takes a topic, not "do this for every trend"),
    but script -> video is not optional once you've decided on a topic.

    Each stage gets a few automatic retries (RETRY_MAX_ATTEMPTS, with
    exponential backoff) before it's recorded as failed — a transient
    network blip or provider rate limit used to just fail the whole run
    on the first hit.
    """
    from faceless_pipeline.db import SessionLocal
    from faceless_pipeline.modules.automation.retry import run_with_retries
    from faceless_pipeline.modules.scripts.generator import generate_script
    from faceless_pipeline.modules.video.run import assemble_pipeline

    def _job():
        db = SessionLocal()
        try:
            script = run_with_retries(generate_script, db, topic=topic, style=style, length_variant=length_variant)
            record_run("script", "success", f"generated for '{topic}'")
        except Exception as exc:
            record_run("script", "error", str(exc))
            db.close()
            return
        try:
            run_with_retries(assemble_pipeline, db, script.id)
            record_run("video", "success", f"assembled for '{topic}'")
        except Exception as exc:
            record_run("video", "error", str(exc))
        finally:
            db.close()

    if background_tasks is not None:
        background_tasks.add_task(_job)
    else:
        _job()
    return {"triggered": "script", "topic": topic}
