from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, field_validator
from sqlalchemy.orm import Session, joinedload

from faceless_pipeline.db import get_db
from faceless_pipeline.models import Video, VideoStatus
from faceless_pipeline.modules.publisher.run import publish_video

router = APIRouter()


class PublishRequest(BaseModel):
    platforms: list[str] = ["youtube"]
    scheduled_for: datetime | None = None

    @field_validator("scheduled_for")
    @classmethod
    def _normalize_to_naive_utc(cls, value: datetime | None) -> datetime | None:
        # Every other datetime in this codebase (Trend.created_at,
        # Performance.pulled_at, and datetime.utcnow() itself — used by
        # the scheduler loop to check whether a schedule is due) is
        # naive UTC. A timezone-aware value here (e.g. a client sending
        # `.toISOString()`) would otherwise raise TypeError the moment
        # it's compared against a naive datetime.utcnow(), or get stored
        # inconsistently. Normalize once at the API boundary instead.
        if value is not None and value.tzinfo is not None:
            return value.astimezone(timezone.utc).replace(tzinfo=None)
        return value


@router.get("/history")
def publish_history(db: Session = Depends(get_db)):
    videos = (
        db.query(Video)
        .options(joinedload(Video.script))
        .filter(Video.status == VideoStatus.published)
        .order_by(Video.created_at.desc())
        .all()
    )
    return [
        {
            "id": v.id,
            "topic": v.script.topic,
            "platform_ids": v.platform_ids,
            "created_at": v.created_at,
        }
        for v in videos
    ]


@router.post("/{video_id}")
def publish(video_id: int, req: PublishRequest, db: Session = Depends(get_db)):
    try:
        video = publish_video(db, video_id, platforms=req.platforms, scheduled_for=req.scheduled_for)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {"id": video.id, "status": video.status, "platform_ids": video.platform_ids}
