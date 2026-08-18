"""Normalize audio loudness before handoff to video assembly.

Uses ffmpeg's loudnorm filter (EBU R128) targeting a typical short-form
platform loudness of -14 LUFS. Requires ffmpeg on PATH.
"""
import logging
import subprocess

from faceless_pipeline.config import settings

logger = logging.getLogger(__name__)


def normalize_loudness(in_path: str, out_path: str, target_lufs: float = -14.0) -> str:
    cmd = [
        settings.ffmpeg_binary,
        "-y",
        "-i",
        in_path,
        "-af",
        f"loudnorm=I={target_lufs}:TP=-1.5:LRA=11",
        # loudnorm's true-peak (TP) analysis oversamples internally, and
        # without an explicit output rate ffmpeg can leave the stream at
        # that oversampled rate (observed: 192kHz from a 24kHz input).
        # That also flips the wav header to WAVE_FORMAT_EXTENSIBLE, which
        # Python's stdlib `wave` module can't parse — silently breaking
        # video/captions.audio_duration_seconds() downstream. Pin to a
        # standard rate so the output stays plain PCM.
        "-ar",
        "48000",
        out_path,
    ]
    logger.info("Normalizing loudness: %s", " ".join(cmd))
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=settings.ffmpeg_timeout_seconds
        )
    except subprocess.TimeoutExpired as exc:
        logger.error("ffmpeg loudnorm timed out after %ss", settings.ffmpeg_timeout_seconds)
        raise RuntimeError(f"ffmpeg loudnorm timed out after {settings.ffmpeg_timeout_seconds}s") from exc
    if result.returncode != 0:
        logger.error("ffmpeg loudnorm failed: %s", result.stderr)
        raise RuntimeError(f"ffmpeg loudnorm failed: {result.stderr[-2000:]}")
    return out_path
