"""Module 5: Review checkpoint. The one place a human touches the
pipeline before anything goes public.
"""
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from faceless_pipeline.db import get_db
from faceless_pipeline.models import Script, Video, VideoStatus

router = APIRouter()


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
    query = db.query(Video).order_by(Video.created_at.desc())
    if status:
        query = query.filter(Video.status == status)
    return [_serialize(v) for v in query.all()]


@router.get("/{video_id}")
def get_video(video_id: int, db: Session = Depends(get_db)):
    video = db.get(Video, video_id)
    if video is None:
        raise HTTPException(status_code=404, detail="Video not found")
    return _serialize(video)


@router.post("/{video_id}/approve")
def approve_video(video_id: int, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    video = db.get(Video, video_id)
    if video is None:
        raise HTTPException(status_code=404, detail="Video not found")

    video.status = VideoStatus.approved
    db.commit()

    def _publish_job():
        from faceless_pipeline.db import SessionLocal
        from faceless_pipeline.modules.publisher.run import publish_video

        session = SessionLocal()
        try:
            publish_video(session, video_id)
        except Exception:
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
def regenerate_video(video_id: int, req: RegenerateRequest, db: Session = Depends(get_db)):
    """Sends the video back to Module 2 (script rewrite) or Module 4
    (re-assemble video) with a feedback note."""
    video = db.get(Video, video_id)
    if video is None:
        raise HTTPException(status_code=404, detail="Video not found")

    if req.target == "script":
        from faceless_pipeline.modules.scripts.generator import regenerate_with_feedback
        from faceless_pipeline.modules.video.run import assemble_pipeline

        new_script = regenerate_with_feedback(db, video.script_id, req.note)
        video.status = VideoStatus.rejected
        video.review_note = f"Sent back for script rewrite: {req.note}"
        db.commit()
        # Also re-assemble the video against the rewritten script, so a
        # rewrite lands back in the review queue like a video regenerate
        # does, instead of leaving the new script with nothing to review.
        new_video = assemble_pipeline(db, new_script.id)
        return {"regenerated": "script", "new_script_id": new_script.id, "new_video_id": new_video.id}

    if req.target == "video":
        from faceless_pipeline.modules.video.run import assemble_pipeline

        video.status = VideoStatus.rejected
        video.review_note = f"Sent back for re-assembly: {req.note}"
        db.commit()
        new_video = assemble_pipeline(db, video.script_id)
        return {"regenerated": "video", "new_video_id": new_video.id}

    raise HTTPException(status_code=400, detail="target must be 'script' or 'video'")


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
