"""Pipeline status + manual trigger endpoints (backs the Module 7 dashboard's
'last run time/status per stage' view and 'run trend finder now' style buttons).
"""
from datetime import datetime

from fastapi import APIRouter, BackgroundTasks

router = APIRouter()

# In-memory run log for MVP. Swap for a `pipeline_runs` table if this needs
# to survive restarts or be queried historically.
_last_runs: dict[str, dict] = {}


def record_run(stage: str, status: str, detail: str = ""):
    _last_runs[stage] = {
        "stage": stage,
        "status": status,
        "detail": detail,
        "at": datetime.utcnow().isoformat(),
    }


@router.get("/status")
def pipeline_status():
    return {"stages": list(_last_runs.values())}


@router.post("/trigger/trends")
def trigger_trend_finder(background_tasks: BackgroundTasks):
    from app.modules.trends.run import run_trend_finder

    def _job():
        try:
            trends = run_trend_finder()
            record_run("trends", "success", f"{len(trends)} new topics")
        except Exception as exc:  # surfaced in the dashboard's status view
            record_run("trends", "error", str(exc))

    background_tasks.add_task(_job)
    return {"triggered": "trends"}


@router.post("/trigger/script")
def trigger_script_generation(topic: str, style: str = "explainer", length_variant: str = "30s", background_tasks: BackgroundTasks = None):
    from app.db import SessionLocal
    from app.modules.scripts.generator import generate_script

    def _job():
        db = SessionLocal()
        try:
            generate_script(db, topic=topic, style=style, length_variant=length_variant)
            record_run("script", "success", f"generated for '{topic}'")
        except Exception as exc:
            record_run("script", "error", str(exc))
        finally:
            db.close()

    if background_tasks is not None:
        background_tasks.add_task(_job)
    else:
        _job()
    return {"triggered": "script", "topic": topic}
