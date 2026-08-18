from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Trend

router = APIRouter()


@router.get("")
def list_trends(used: bool | None = None, limit: int = 100, db: Session = Depends(get_db)):
    query = db.query(Trend).order_by(Trend.score.desc())
    if used is not None:
        query = query.filter(Trend.used == used)
    trends = query.limit(limit).all()
    return [
        {
            "id": t.id,
            "topic": t.topic,
            "source": t.source,
            "score": t.score,
            "used": t.used,
            "created_at": t.created_at,
        }
        for t in trends
    ]
