from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from faceless_pipeline.db import get_db
from faceless_pipeline.models import Script
from faceless_pipeline.modules.scripts.generator import generate_script, regenerate_with_feedback
from faceless_pipeline.modules.scripts.presets import DEFAULT_LENGTH, DEFAULT_STYLE

router = APIRouter()


class GenerateRequest(BaseModel):
    topic: str
    style: str = DEFAULT_STYLE
    length_variant: str = DEFAULT_LENGTH
    trend_id: int | None = None
    allow_duplicate: bool = False


class RegenerateRequest(BaseModel):
    feedback_note: str


def _serialize(script: Script) -> dict:
    return {
        "id": script.id,
        "topic": script.topic,
        "script": script.script,
        "style": script.style,
        "length_variant": script.length_variant,
        "status": script.status,
        "parent_script_id": script.parent_script_id,
        "created_at": script.created_at,
    }


@router.get("")
def list_scripts(topic: str | None = None, limit: int = 100, db: Session = Depends(get_db)):
    query = db.query(Script).order_by(Script.created_at.desc())
    if topic:
        query = query.filter(Script.topic.ilike(f"%{topic}%"))
    return [_serialize(s) for s in query.limit(limit).all()]


@router.post("")
def create_script(req: GenerateRequest, db: Session = Depends(get_db)):
    try:
        script = generate_script(
            db,
            topic=req.topic,
            style=req.style,
            length_variant=req.length_variant,
            trend_id=req.trend_id,
            allow_duplicate=req.allow_duplicate,
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    return _serialize(script)


@router.post("/{script_id}/regenerate")
def regenerate_script(script_id: int, req: RegenerateRequest, db: Session = Depends(get_db)):
    try:
        script = regenerate_with_feedback(db, script_id, req.feedback_note)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    return _serialize(script)
