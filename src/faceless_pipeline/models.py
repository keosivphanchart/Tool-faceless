import enum
from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, Enum, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from faceless_pipeline.db import Base


class VideoStatus(str, enum.Enum):
    pending = "pending"
    approved = "approved"
    rejected = "rejected"
    published = "published"


class Trend(Base):
    __tablename__ = "trends"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    topic: Mapped[str] = mapped_column(String(500), index=True)
    normalized_topic: Mapped[str] = mapped_column(String(500), index=True)
    source: Mapped[str] = mapped_column(String(50))  # google_trends | youtube | reddit
    score: Mapped[float] = mapped_column(Float, default=0.0)
    used: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    scripts: Mapped[list["Script"]] = relationship(back_populates="trend")


class Script(Base):
    __tablename__ = "scripts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    trend_id: Mapped[int | None] = mapped_column(ForeignKey("trends.id"), nullable=True)
    topic: Mapped[str] = mapped_column(String(500))
    script: Mapped[dict] = mapped_column(JSON)  # {hook, promise, body, payoff, cta}
    style: Mapped[str] = mapped_column(String(50), default="explainer")
    length_variant: Mapped[str] = mapped_column(String(10), default="30s")
    status: Mapped[str] = mapped_column(String(20), default="draft")
    feedback_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    parent_script_id: Mapped[int | None] = mapped_column(ForeignKey("scripts.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    trend: Mapped["Trend | None"] = relationship(back_populates="scripts")
    videos: Mapped[list["Video"]] = relationship(back_populates="script")


class Video(Base):
    __tablename__ = "videos"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    script_id: Mapped[int] = mapped_column(ForeignKey("scripts.id"))
    file_path: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    thumbnail_path: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    audio_path: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    captions_path: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    metadata_path: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    status: Mapped[str] = mapped_column(
        Enum(VideoStatus, native_enum=False), default=VideoStatus.pending
    )
    review_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    platform_ids: Mapped[dict] = mapped_column(JSON, default=dict)  # {"youtube": "...", "tiktok": "..."}
    scheduled_for: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    script: Mapped["Script"] = relationship(back_populates="videos")
    performance: Mapped[list["Performance"]] = relationship(back_populates="video")


class Performance(Base):
    __tablename__ = "performance"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    video_id: Mapped[int] = mapped_column(ForeignKey("videos.id"))
    platform: Mapped[str] = mapped_column(String(50))
    views: Mapped[int] = mapped_column(Integer, default=0)
    retention_pct: Mapped[float] = mapped_column(Float, default=0.0)
    completion_pct: Mapped[float] = mapped_column(Float, default=0.0)
    likes: Mapped[int] = mapped_column(Integer, default=0)
    shares: Mapped[int] = mapped_column(Integer, default=0)
    pulled_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    video: Mapped["Video"] = relationship(back_populates="performance")
