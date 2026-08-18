"""Module 6 orchestrator: publish an approved video, immediately or on a
schedule, and record publish history / platform video IDs.
"""
import json
import logging
from datetime import datetime
from pathlib import Path

from sqlalchemy.orm import Session

from faceless_pipeline.models import Video, VideoStatus
from faceless_pipeline.modules.publisher.tiktok import TikTokNotConfigured
from faceless_pipeline.modules.publisher.tiktok import upload_video as tiktok_upload
from faceless_pipeline.modules.publisher.youtube import YouTubeQuotaExceeded
from faceless_pipeline.modules.publisher.youtube import upload_video as youtube_upload

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def _load_metadata(video: Video) -> dict:
    if video.metadata_path and Path(video.metadata_path).exists():
        return json.loads(Path(video.metadata_path).read_text(encoding="utf-8"))
    return {"title": video.script.topic, "description": "", "tags": []}


def publish_video(db: Session, video_id: int, platforms: list[str] | None = None, scheduled_for: datetime | None = None) -> Video:
    video = db.get(Video, video_id)
    if video is None:
        raise ValueError(f"Video {video_id} not found")
    if video.status != VideoStatus.approved:
        raise ValueError(f"Video {video_id} must be approved before publishing (status={video.status})")
    if not video.file_path or not Path(video.file_path).exists():
        raise ValueError(f"Video {video_id} has no rendered file at {video.file_path}")

    if scheduled_for:
        video.scheduled_for = scheduled_for
        db.commit()
        logger.info("Video %s queued for %s (dispatch it again at that time)", video_id, scheduled_for)
        return video

    platforms = platforms or ["youtube"]
    metadata = _load_metadata(video)
    platform_ids = dict(video.platform_ids or {})

    for platform in platforms:
        try:
            if platform == "youtube":
                video_ref = youtube_upload(
                    video.file_path,
                    title=metadata.get("title", video.script.topic),
                    description=metadata.get("description", ""),
                    tags=metadata.get("tags", []),
                )
                platform_ids["youtube"] = video_ref
            elif platform == "tiktok":
                video_ref = tiktok_upload(
                    video.file_path, title=metadata.get("title", video.script.topic), tags=metadata.get("tags", [])
                )
                platform_ids["tiktok"] = video_ref
            else:
                logger.warning("Unknown platform '%s', skipping", platform)
        except YouTubeQuotaExceeded:
            logger.exception("YouTube quota exceeded; leave video approved and retry later")
        except TikTokNotConfigured:
            logger.warning("TikTok not configured yet; skipping TikTok publish")
        except Exception:
            logger.exception("Publish to %s failed", platform)

    video.platform_ids = platform_ids
    if platform_ids:
        video.status = VideoStatus.published
    db.commit()
    db.refresh(video)
    return video


if __name__ == "__main__":
    import argparse

    from faceless_pipeline.db import SessionLocal, init_db

    parser = argparse.ArgumentParser()
    parser.add_argument("video_id", type=int)
    parser.add_argument("--platforms", nargs="+", default=["youtube"])
    args = parser.parse_args()

    init_db()
    session = SessionLocal()
    try:
        result = publish_video(session, args.video_id, platforms=args.platforms)
        print(f"Video {result.id} status={result.status} platform_ids={result.platform_ids}")
    finally:
        session.close()
