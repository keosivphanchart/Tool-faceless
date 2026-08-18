from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Performance
from app.modules.analytics.run import best_performing_patterns, pull_all_performance

router = APIRouter()


@router.get("/performance")
def list_performance(video_id: int | None = None, db: Session = Depends(get_db)):
    query = db.query(Performance).order_by(Performance.pulled_at.desc())
    if video_id is not None:
        query = query.filter(Performance.video_id == video_id)
    rows = query.limit(200).all()
    return [
        {
            "id": p.id,
            "video_id": p.video_id,
            "platform": p.platform,
            "views": p.views,
            "retention_pct": p.retention_pct,
            "completion_pct": p.completion_pct,
            "likes": p.likes,
            "shares": p.shares,
            "pulled_at": p.pulled_at,
        }
        for p in rows
    ]


@router.get("/best-performers")
def best_performers(db: Session = Depends(get_db)):
    return best_performing_patterns(db)


@router.post("/pull")
def trigger_pull(db: Session = Depends(get_db)):
    count = pull_all_performance(db)
    return {"pulled": count}
