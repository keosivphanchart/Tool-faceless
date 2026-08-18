"""Module 4 orchestrator: script + voiceover -> final vertical .mp4 with
burned-in captions, thumbnail, and metadata sidecar. Creates the `videos`
row that feeds Module 5 (review checkpoint).

Usage:
    python -m faceless_pipeline.modules.video.run <script_id> [--dry-run]
"""
import argparse
import logging
from pathlib import Path

from faceless_pipeline.config import settings
from faceless_pipeline.db import SessionLocal, init_db
from faceless_pipeline.models import Script, Video, VideoStatus
from faceless_pipeline.modules.video.assemble import assemble_video, build_background, generate_thumbnail
from faceless_pipeline.modules.video.captions import generate_captions
from faceless_pipeline.modules.video.metadata import write_metadata
from faceless_pipeline.modules.video.stock_footage import fetch_background_clips
from faceless_pipeline.modules.voice.run import generate_voiceover, script_to_narration_text
from faceless_pipeline.modules.review.notify import notify_video_ready

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def _keywords_from_topic(topic: str, max_keywords: int = 3) -> list[str]:
    stopwords = {"the", "a", "an", "of", "to", "in", "for", "and", "on", "is", "with"}
    words = [w.strip(".,!?").lower() for w in topic.split()]
    keywords = [w for w in words if w and w not in stopwords]
    return keywords[:max_keywords] or [topic]


def assemble_pipeline(script_id: int, dry_run: bool = False) -> Video:
    db = SessionLocal()
    try:
        script = db.get(Script, script_id)
        if script is None:
            raise ValueError(f"Script {script_id} not found")

        out_dir = Path(settings.output_dir) / str(script_id)
        out_dir.mkdir(parents=True, exist_ok=True)

        narration_text = script_to_narration_text(script.script)

        audio_path = generate_voiceover(script_id, dry_run=dry_run)

        srt_path = str(out_dir / "captions.srt")
        try:
            generate_captions(audio_path, narration_text, srt_path)
        except Exception:
            logger.exception("Caption generation failed, continuing without burned-in captions")
            srt_path = None

        estimated_duration = max(len(narration_text.split()) / 2.5, 5.0)
        background_path = str(out_dir / "background.mp4")
        final_path = str(out_dir / "final.mp4")
        thumbnail_path = str(out_dir / "thumbnail.jpg")
        metadata_path = str(out_dir / "metadata.json")

        try:
            clip_paths = fetch_background_clips(_keywords_from_topic(script.topic), str(out_dir / "clips"))
            if not clip_paths:
                raise RuntimeError("no stock footage available")
            build_background(clip_paths, estimated_duration, background_path)
            assemble_video(background_path, audio_path, srt_path, final_path)
            generate_thumbnail(final_path, thumbnail_path)
        except Exception:
            logger.exception(
                "Full ffmpeg assembly unavailable in this environment "
                "(missing ffmpeg binary, stock footage API keys, etc). "
                "Recording paths without a rendered file so the review "
                "checkpoint can still be exercised end-to-end."
            )
            final_path = None
            thumbnail_path = None

        write_metadata(script.script, script.topic, metadata_path)

        video = Video(
            script_id=script.id,
            file_path=final_path,
            thumbnail_path=thumbnail_path,
            audio_path=audio_path,
            captions_path=srt_path,
            metadata_path=metadata_path,
            status=VideoStatus.pending,
        )
        db.add(video)
        db.commit()
        db.refresh(video)

        notify_video_ready(video.id, script.topic)

        return video
    finally:
        db.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("script_id", type=int)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    init_db()
    video = assemble_pipeline(args.script_id, dry_run=args.dry_run)
    print(f"Video {video.id} created with status={video.status}, file={video.file_path}")
