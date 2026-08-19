"""Opt-in auto-approve: skips the human review click for a video that
passes a few basic safety checks, immediately doing what a manual
Approve click would. Off by default (AUTO_APPROVE_ENABLED) - Module 5's
"one mandatory human checkpoint" stays the default behavior unless this
is deliberately turned on.
"""
import logging
from pathlib import Path

from sqlalchemy.orm import Session

from faceless_pipeline.config import settings
from faceless_pipeline.models import Video, VideoStatus

logger = logging.getLogger(__name__)


def passes_auto_approve_checks(video: Video) -> tuple[bool, str]:
    """Returns (passed, reason) - reason explains a failure, empty on success."""
    if not video.file_path or not Path(video.file_path).exists():
        return False, "no rendered video file"

    storyboard = (video.script.script or {}).get("storyboard") or []
    if len(storyboard) != 5:
        return False, f"storyboard has {len(storyboard)} shots, expected 5"

    if settings.auto_approve_min_audio_seconds > 0 and video.audio_path and Path(video.audio_path).exists():
        from faceless_pipeline.modules.video.captions import audio_duration_seconds

        duration = audio_duration_seconds(video.audio_path)
        if duration < settings.auto_approve_min_audio_seconds:
            return False, f"audio duration {duration:.1f}s below minimum {settings.auto_approve_min_audio_seconds}s"

    return True, ""


def maybe_auto_approve(db: Session, video_id: int) -> bool:
    """If AUTO_APPROVE_ENABLED and the video passes checks, approves it
    and kicks off publish (same as the dashboard's Approve button),
    returning True. No-op (returns False) otherwise, leaving the video
    pending for a human as usual.
    """
    if not settings.auto_approve_enabled:
        return False

    video = db.get(Video, video_id)
    if video is None or video.status != VideoStatus.pending:
        return False

    passed, reason = passes_auto_approve_checks(video)
    if not passed:
        logger.info("Video %s did not pass auto-approve checks: %s", video_id, reason)
        return False

    video.status = VideoStatus.approved
    db.commit()

    from faceless_pipeline.api.pipeline import record_run
    from faceless_pipeline.modules.publisher.run import publish_video

    try:
        published = publish_video(db, video_id)
        if published.platform_ids:
            platforms = ", ".join(str(p) for p in published.platform_ids)
            record_run("publish", "success", f"video {video_id} auto-approved -> {platforms}")
        else:
            record_run("publish", "error", f"video {video_id}: auto-approved but no platform accepted the upload")
    except Exception as exc:
        record_run("publish", "error", f"video {video_id}: auto-approve publish failed: {exc}")
        logger.exception("Auto-approve publish failed for video %s", video_id)

    return True
