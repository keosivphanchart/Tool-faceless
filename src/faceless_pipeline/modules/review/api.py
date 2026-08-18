"""Module 5: Review checkpoint. The one place a human touches the
pipeline before anything goes public.
"""
from datetime import datetime, timezone

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel, field_validator
from sqlalchemy.orm import Session, joinedload

from faceless_pipeline.db import get_db
from faceless_pipeline.models import Script, Video, VideoStatus

router = APIRouter()


class ApproveRequest(BaseModel):
    scheduled_for: datetime | None = None

    @field_validator("scheduled_for")
    @classmethod
    def _normalize_to_naive_utc(cls, value: datetime | None) -> datetime | None:
        # The dashboard sends `new Date(...).toISOString()`, which is
        # timezone-aware (a "Z" offset) — but every other datetime in
        # this codebase (Trend.created_at, Performance.pulled_at, and
        # datetime.utcnow() itself, used to check whether a schedule is
        # due) is naive UTC. Comparing an aware and a naive datetime
        # raises TypeError, so normalize once here rather than at every
        # comparison site downstream.
        if value is not None and value.tzinfo is not None:
            return value.astimezone(timezone.utc).replace(tzinfo=None)
        return value


class RejectRequest(BaseModel):
    note: str | None = None


class RegenerateRequest(BaseModel):
    target: str  # "script" | "video"
    note: str


class ScriptEditRequest(BaseModel):
    hook: str | None = None
    promise: str | None = None
    body: str | None = None
    payoff: str | None = None
    cta: str | None = None


def _serialize(video: Video) -> dict:
    return {
        "id": video.id,
        "status": video.status,
        "file_path": video.file_path,
        "thumbnail_path": video.thumbnail_path,
        "audio_path": video.audio_path,
        "captions_path": video.captions_path,
        "metadata_path": video.metadata_path,
        "review_note": video.review_note,
        "scheduled_for": video.scheduled_for,
        "created_at": video.created_at,
        "script": {
            "id": video.script.id,
            "topic": video.script.topic,
            "style": video.script.style,
            "length_variant": video.script.length_variant,
            "text": video.script.script,
        },
    }


@router.get("")
def list_videos(status: str | None = "pending", db: Session = Depends(get_db)):
    # joinedload avoids an N+1: without it, _serialize()'s video.script
    # access below fires one extra SELECT per video in the list.
    query = db.query(Video).options(joinedload(Video.script)).order_by(Video.created_at.desc())
    if status:
        query = query.filter(Video.status == status)
    return [_serialize(v) for v in query.all()]


@router.get("/scheduled/upcoming")
def list_scheduled(db: Session = Depends(get_db)):
    """Approved videos waiting on a future scheduled_for — the only place
    a scheduled video is visible after it leaves the pending review
    queue and before it actually publishes, since list_videos(status=...)
    only ever shows one status at a time."""
    videos = (
        db.query(Video)
        .options(joinedload(Video.script))
        .filter(Video.status == VideoStatus.approved, Video.scheduled_for.isnot(None))
        .order_by(Video.scheduled_for.asc())
        .all()
    )
    return [_serialize(v) for v in videos]


@router.post("/{video_id}/unschedule")
def unschedule_video(video_id: int, db: Session = Depends(get_db)):
    """Cancels a pending schedule without touching review status — the
    video stays approved (so it can be published immediately or given a
    new schedule), it just won't be picked up by the scheduler loop."""
    video = db.get(Video, video_id)
    if video is None:
        raise HTTPException(status_code=404, detail="Video not found")
    if video.scheduled_for is None:
        raise HTTPException(status_code=400, detail="Video has no pending schedule")

    video.scheduled_for = None
    db.commit()
    return _serialize(video)


@router.get("/{video_id}")
def get_video(video_id: int, db: Session = Depends(get_db)):
    video = db.query(Video).options(joinedload(Video.script)).filter(Video.id == video_id).first()
    if video is None:
        raise HTTPException(status_code=404, detail="Video not found")
    return _serialize(video)


@router.post("/{video_id}/approve")
def approve_video(
    video_id: int,
    background_tasks: BackgroundTasks,
    req: ApproveRequest = ApproveRequest(),
    db: Session = Depends(get_db),
):
    video = db.get(Video, video_id)
    if video is None:
        raise HTTPException(status_code=404, detail="Video not found")
    if req.scheduled_for and req.scheduled_for <= datetime.utcnow():
        raise HTTPException(status_code=400, detail="scheduled_for must be in the future")

    video.status = VideoStatus.approved
    db.commit()

    def _publish_job():
        from faceless_pipeline.api.pipeline import record_run
        from faceless_pipeline.db import SessionLocal
        from faceless_pipeline.modules.publisher.run import publish_video

        session = SessionLocal()
        try:
            published = publish_video(session, video_id, scheduled_for=req.scheduled_for)
            if req.scheduled_for:
                # publish_video() just stores scheduled_for and returns
                # for a future timestamp - the scheduler loop (started
                # from main.py's lifespan) is what actually publishes it
                # once that time arrives.
                record_run("publish", "success", f"video {video_id} scheduled for {req.scheduled_for.isoformat()}")
            elif published.platform_ids:
                platforms = ", ".join(str(p) for p in published.platform_ids)
                record_run("publish", "success", f"video {video_id} -> {platforms}")
            else:
                # publish_video() itself swallows per-platform failures so
                # one bad platform doesn't block the others - if nothing
                # published, that's the dashboard-visible signal something
                # needs attention (check server logs for which platform).
                record_run("publish", "error", f"video {video_id}: no platform accepted the upload")
        except Exception as exc:
            record_run("publish", "error", f"video {video_id}: {exc}")
            import logging

            logging.getLogger(__name__).exception("Auto-publish after approval failed for video %s", video_id)
        finally:
            session.close()

    background_tasks.add_task(_publish_job)
    return _serialize(video)


@router.post("/{video_id}/reject")
def reject_video(video_id: int, req: RejectRequest, db: Session = Depends(get_db)):
    video = db.get(Video, video_id)
    if video is None:
        raise HTTPException(status_code=404, detail="Video not found")

    video.status = VideoStatus.rejected
    video.review_note = req.note
    db.commit()
    return _serialize(video)


@router.post("/{video_id}/regenerate")
def regenerate_video(video_id: int, req: RegenerateRequest, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    """Sends the video back to Module 2 (script rewrite) or Module 4
    (re-assemble video) with a feedback note.

    The rewrite (a Claude API call) and/or reassembly (TTS + ffmpeg) can
    each take anywhere from seconds to minutes, so — like approve_video's
    publish step — the actual work runs as a background task on its own
    session; the request just records the rejection and returns. The new
    script/video aren't known synchronously, so poll the review queue
    (GET /videos?status=pending) to see the result land.
    """
    if req.target not in ("script", "video"):
        raise HTTPException(status_code=400, detail="target must be 'script' or 'video'")

    video = db.get(Video, video_id)
    if video is None:
        raise HTTPException(status_code=404, detail="Video not found")

    script_id = video.script_id
    video.status = VideoStatus.rejected
    video.review_note = (
        f"Sent back for {'script rewrite' if req.target == 'script' else 're-assembly'}: {req.note}"
    )
    db.commit()

    def _regenerate_job():
        from faceless_pipeline.api.pipeline import record_run
        from faceless_pipeline.db import SessionLocal

        session = SessionLocal()
        try:
            target_script_id = script_id
            if req.target == "script":
                from faceless_pipeline.modules.scripts.generator import regenerate_with_feedback

                new_script = regenerate_with_feedback(session, script_id, req.note)
                target_script_id = new_script.id

            from faceless_pipeline.modules.video.run import assemble_pipeline

            assemble_pipeline(session, target_script_id)
            record_run("regenerate", "success", f"video {video_id} (target={req.target}) regenerated")
        except Exception as exc:
            record_run("regenerate", "error", f"video {video_id} (target={req.target}): {exc}")
            import logging

            logging.getLogger(__name__).exception(
                "Regenerate job failed for video %s (target=%s)", video_id, req.target
            )
        finally:
            session.close()

    background_tasks.add_task(_regenerate_job)
    return {"regenerating": req.target, "status": "queued", "video_id": video_id}


@router.patch("/{video_id}/script")
def edit_script(video_id: int, req: ScriptEditRequest, db: Session = Depends(get_db)):
    """Light edit capability for script text before approval."""
    video = db.get(Video, video_id)
    if video is None:
        raise HTTPException(status_code=404, detail="Video not found")

    script = db.get(Script, video.script_id)
    updated = dict(script.script)
    for field in ("hook", "promise", "body", "payoff", "cta"):
        value = getattr(req, field)
        if value is not None:
            updated[field] = value
    script.script = updated
    db.commit()
    return _serialize(video)
