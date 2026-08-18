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
        out_path,
    ]
    logger.info("Normalizing loudness: %s", " ".join(cmd))
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        logger.error("ffmpeg loudnorm failed: %s", result.stderr)
        raise RuntimeError(f"ffmpeg loudnorm failed: {result.stderr[-2000:]}")
    return out_path
