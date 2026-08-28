from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, field_validator
from sqlalchemy.orm import Session

from faceless_pipeline.db import get_db
from faceless_pipeline.models import PostingSlot

router = APIRouter()

VALID_PLATFORMS = {"youtube", "tiktok"}


def _validate_days(value: list[int]) -> list[int]:
    if not value:
        raise ValueError("days_of_week can't be empty")
    if any(d < 0 or d > 6 for d in value):
        raise ValueError("days_of_week entries must be 0 (Monday) through 6 (Sunday)")
    return sorted(set(value))


def _validate_time(value: str) -> str:
    import re

    if not re.fullmatch(r"([01]\d|2[0-3]):[0-5]\d", value):
        raise ValueError("time_of_day must be HH:MM, 24h, e.g. '18:00'")
    return value


def _validate_platforms(value: list[str] | None) -> list[str] | None:
    if value is None:
        return None
    invalid = set(value) - VALID_PLATFORMS
    if invalid:
        raise ValueError(f"Unknown platform(s): {', '.join(sorted(invalid))}")
    return value or None


class SlotCreate(BaseModel):
    label: str = ""
    days_of_week: list[int]
    time_of_day: str
    platforms: list[str] | None = None
    enabled: bool = True

    _v_days = field_validator("days_of_week")(_validate_days)
    _v_time = field_validator("time_of_day")(_validate_time)
    _v_platforms = field_validator("platforms")(_validate_platforms)


class SlotUpdate(BaseModel):
    label: str | None = None
    days_of_week: list[int] | None = None
    time_of_day: str | None = None
    platforms: list[str] | None = None
    enabled: bool | None = None

    _v_days = field_validator("days_of_week")(lambda v: _validate_days(v) if v is not None else v)
    _v_time = field_validator("time_of_day")(lambda v: _validate_time(v) if v is not None else v)
    _v_platforms = field_validator("platforms")(_validate_platforms)


def _serialize(slot: PostingSlot) -> dict:
    return {
        "id": slot.id,
        "label": slot.label,
        "days_of_week": slot.days_of_week,
        "time_of_day": slot.time_of_day,
        "platforms": slot.platforms,
        "enabled": slot.enabled,
        "last_fired_date": slot.last_fired_date,
        "created_at": slot.created_at,
    }


@router.get("")
def list_slots(db: Session = Depends(get_db)):
    slots = db.query(PostingSlot).order_by(PostingSlot.time_of_day.asc()).all()
    return [_serialize(s) for s in slots]


@router.post("")
def create_slot(payload: SlotCreate, db: Session = Depends(get_db)):
    slot = PostingSlot(**payload.model_dump())
    db.add(slot)
    db.commit()
    db.refresh(slot)
    return _serialize(slot)


@router.patch("/{slot_id}")
def update_slot(slot_id: int, payload: SlotUpdate, db: Session = Depends(get_db)):
    slot = db.get(PostingSlot, slot_id)
    if slot is None:
        raise HTTPException(status_code=404, detail="Posting slot not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(slot, field, value)
    db.commit()
    db.refresh(slot)
    return _serialize(slot)


@router.delete("/{slot_id}")
def delete_slot(slot_id: int, db: Session = Depends(get_db)):
    slot = db.get(PostingSlot, slot_id)
    if slot is None:
        raise HTTPException(status_code=404, detail="Posting slot not found")
    db.delete(slot)
    db.commit()
    return {"deleted": True}
