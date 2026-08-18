"""FFmpeg pipeline: background clip(s) + voiceover + burned-in captions,
output vertical 9:16, with royalty-free background music mixed under the
voiceover. Requires the `ffmpeg` binary on PATH (FFMPEG_BINARY env var).
"""
import logging
import subprocess
from pathlib import Path

from app.config import settings

logger = logging.getLogger(__name__)

TARGET_WIDTH = 1080
TARGET_HEIGHT = 1920


def _run(cmd: list[str]) -> None:
    logger.info("Running: %s", " ".join(cmd))
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        logger.error("ffmpeg command failed: %s", result.stderr)
        raise RuntimeError(f"ffmpeg failed: {result.stderr[-2000:]}")


def build_background(clip_paths: list[str], duration_seconds: float, out_path: str) -> str:
    """Concatenates/loops background clips to cover `duration_seconds`,
    scaled and center-cropped to a 9:16 frame."""
    if not clip_paths:
        raise ValueError("No background clips provided")

    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    concat_list_path = str(Path(out_path).with_suffix(".concat.txt"))

    # Loop the clip list until it covers the target duration; ffmpeg's
    # concat demuxer handles the actual stitching.
    lines = []
    total = 0.0
    idx = 0
    # Rough per-clip estimate; real duration is enforced by -t on the output.
    assumed_clip_len = 6.0
    while total < duration_seconds:
        clip = clip_paths[idx % len(clip_paths)]
        lines.append(f"file '{Path(clip).resolve()}'")
        total += assumed_clip_len
        idx += 1
    Path(concat_list_path).write_text("\n".join(lines), encoding="utf-8")

    cmd = [
        settings.ffmpeg_binary,
        "-y",
        "-f",
        "concat",
        "-safe",
        "0",
        "-i",
        concat_list_path,
        "-t",
        str(duration_seconds),
        "-vf",
        f"scale={TARGET_WIDTH}:{TARGET_HEIGHT}:force_original_aspect_ratio=increase,"
        f"crop={TARGET_WIDTH}:{TARGET_HEIGHT}",
        "-an",
        out_path,
    ]
    _run(cmd)
    return out_path


def assemble_video(
    background_path: str,
    voiceover_path: str,
    srt_path: str | None,
    out_path: str,
    music_path: str | None = None,
    music_volume_db: float = -18.0,
) -> str:
    """Combines background video + voiceover (+ optional music, +
    optional burned-in captions) into the final output."""
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)

    inputs = ["-i", background_path, "-i", voiceover_path]
    filter_parts = []
    audio_map = "1:a"

    if music_path:
        inputs += ["-i", music_path]
        filter_parts.append(
            f"[2:a]volume={music_volume_db}dB,aloop=loop=-1:size=2e9[music]"
        )
        filter_parts.append(f"[1:a][music]amix=inputs=2:duration=first:dropout_transition=2[aout]")
        audio_map = "[aout]"

    video_map = "0:v"
    if srt_path and Path(srt_path).exists():
        escaped_srt = srt_path.replace(":", "\\:")
        filter_parts.append(
            f"[0:v]subtitles='{escaped_srt}':force_style="
            "'FontName=Arial,FontSize=16,PrimaryColour=&HFFFFFF&,"
            "OutlineColour=&H000000&,BorderStyle=3,Outline=2,Alignment=2'[vout]"
        )
        video_map = "[vout]"

    cmd = [settings.ffmpeg_binary, "-y", *inputs]
    if filter_parts:
        cmd += ["-filter_complex", ";".join(filter_parts)]
    cmd += [
        "-map",
        video_map,
        "-map",
        audio_map,
        "-c:v",
        "libx264",
        "-c:a",
        "aac",
        "-shortest",
        out_path,
    ]
    _run(cmd)
    return out_path


def generate_thumbnail(video_path: str, out_path: str, timestamp: str = "00:00:01") -> str:
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        settings.ffmpeg_binary,
        "-y",
        "-ss",
        timestamp,
        "-i",
        video_path,
        "-frames:v",
        "1",
        out_path,
    ]
    _run(cmd)
    return out_path
