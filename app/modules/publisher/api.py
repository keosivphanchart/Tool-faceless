from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Video, VideoStatus
from app.modules.publisher.run import publish_video

router = APIRouter()


class PublishRequest(BaseModel):
    platforms: list[str] = ["youtube"]
    scheduled_for: datetime | None = None


@router.get("/history")
def publish_history(db: Session = Depends(get_db)):
    videos = db.query(Video).filter(Video.status == VideoStatus.published).order_by(Video.created_at.desc()).all()
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
