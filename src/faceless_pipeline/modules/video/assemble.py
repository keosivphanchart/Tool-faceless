"""FFmpeg pipeline: background clip(s) + voiceover + burned-in captions,
output vertical 9:16, with royalty-free background music mixed under the
voiceover. Requires the `ffmpeg` binary on PATH (FFMPEG_BINARY env var).
"""
import logging
import subprocess
from pathlib import Path

from faceless_pipeline.config import settings

logger = logging.getLogger(__name__)

TARGET_WIDTH = 1080
TARGET_HEIGHT = 1920


def run_ffmpeg(cmd: list[str]) -> None:
    """Runs an ffmpeg command with a timeout. Without one, a hung ffmpeg
    process (corrupt input, a filter that never terminates, etc) would
    block whichever thread is running this call forever — and since
    Module 4 is invoked from FastAPI BackgroundTasks, that's a worker
    thread the server needs back, not just a slow CLI call.
    """
    logger.info("Running: %s", " ".join(cmd))
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=settings.ffmpeg_timeout_seconds
        )
    except subprocess.TimeoutExpired as exc:
        logger.error("ffmpeg command timed out after %ss: %s", settings.ffmpeg_timeout_seconds, cmd)
        raise RuntimeError(f"ffmpeg timed out after {settings.ffmpeg_timeout_seconds}s") from exc
    if result.returncode != 0:
        logger.error("ffmpeg command failed: %s", result.stderr)
        raise RuntimeError(f"ffmpeg failed: {result.stderr[-2000:]}")


def _probe_duration(path: str) -> float | None:
    """Real clip duration via ffprobe, or None if it can't be determined
    (corrupt file, ffprobe missing, etc) — callers should treat None as
    "assume it's short" rather than skipping it, so a failed probe biases
    toward looping too much rather than too little.
    """
    cmd = [
        settings.ffprobe_binary,
        "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        path,
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if result.returncode != 0:
            return None
        return float(result.stdout.strip())
    except (subprocess.TimeoutExpired, ValueError, FileNotFoundError):
        return None


def build_background(clip_paths: list[str], duration_seconds: float, out_path: str) -> str:
    """Concatenates/loops background clips to cover `duration_seconds`,
    scaled and center-cropped to a 9:16 frame."""
    if not clip_paths:
        raise ValueError("No background clips provided")

    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    concat_list_path = str(Path(out_path).with_suffix(".concat.txt"))

    # Loop the clip list until it covers the target duration; ffmpeg's
    # concat demuxer handles the actual stitching. Must use each clip's
    # *real* duration here, not a guess: assemble_video() below runs with
    # -shortest, so if this list ends up covering less real content than
    # duration_seconds, the concat demuxer just runs out of frames early
    # and the final video — including the narration audio — gets cut off
    # at whatever the background actually reached. A fixed "assume every
    # clip is ~6s" estimate silently produced a 6s background for a
    # requested 15s duration when the source clips were only 2s each.
    FALLBACK_CLIP_LEN = 2.0  # used when a probe fails; biases toward looping more, not less
    clip_durations = [_probe_duration(c) or FALLBACK_CLIP_LEN for c in clip_paths]

    lines = []
    total = 0.0
    idx = 0
    max_iterations = 10_000  # safety valve against a pathologically tiny reported duration
    while total < duration_seconds and idx < max_iterations:
        clip_index = idx % len(clip_paths)
        lines.append(f"file '{Path(clip_paths[clip_index]).resolve()}'")
        total += max(clip_durations[clip_index], 0.1)
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
    run_ffmpeg(cmd)
    return out_path


def assemble_video(
    background_path: str,
    voiceover_path: str,
    captions_path: str | None,
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
    if captions_path and Path(captions_path).exists():
        # No force_style here: captions.py's words_to_ass() already embeds
        # a [V4+ Styles] section (colors, font, karaoke fill) — force_style
        # would override PrimaryColour/SecondaryColour and kill the
        # word-by-word karaoke highlight it sets up.
        escaped_captions = captions_path.replace(":", "\\:")
        filter_parts.append(f"[0:v]subtitles='{escaped_captions}'[vout]")
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
    run_ffmpeg(cmd)
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
    run_ffmpeg(cmd)
    return out_path
