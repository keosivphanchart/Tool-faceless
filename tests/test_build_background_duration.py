"""Regression test: build_background() must actually reach the requested
duration regardless of how short the source clips are.

Found by running the real ffmpeg pipeline (not the "ffmpeg unavailable"
degraded path most of the suite exercises): the concat list was sized
using a hardcoded `assumed_clip_len = 6.0` guess at how long each clip
is, instead of each clip's real duration. Requesting a 15s background
from a single real 2s clip produced only 6s of output — the concat
demuxer ran out of frames once the *actual* looped content (3 assumed-6s
"slots", each really only 2s) was exhausted, well short of -t 15.0. Since
assemble_video() runs with -shortest, that would have silently truncated
the final video's narration audio to match the undersized background —
the exact failure mode a separate fix (sizing background off the real
audio duration instead of a word-count estimate) was meant to prevent,
reintroduced through the clip-length side instead of the audio-length
side.

Requires a real `ffmpeg`/`ffprobe`; skipped if unavailable.
"""
import shutil
import subprocess

import pytest

pytestmark = pytest.mark.skipif(
    shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None,
    reason="requires real ffmpeg and ffprobe binaries",
)


def _make_clip(path: str, duration: float, color: str = "red") -> str:
    subprocess.run(
        [
            "ffmpeg", "-y", "-f", "lavfi", "-i", f"color=c={color}:size=320x240:duration={duration}:rate=25",
            "-c:v", "libx264", "-pix_fmt", "yuv420p", path,
        ],
        check=True,
        capture_output=True,
    )
    return path


def _probe_duration(path: str) -> float:
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", path],
        check=True,
        capture_output=True,
        text=True,
    )
    return float(result.stdout.strip())


def test_short_clip_looped_reaches_full_requested_duration(tmp_path):
    from faceless_pipeline.modules.video.assemble import build_background

    clip = _make_clip(str(tmp_path / "short.mp4"), duration=2.0)
    out_path = str(tmp_path / "background.mp4")

    build_background([clip], duration_seconds=15.0, out_path=out_path)

    assert _probe_duration(out_path) == pytest.approx(15.0, abs=0.2)


def test_clips_close_to_the_old_hardcoded_assumption_still_work(tmp_path):
    """Regression guard on the normal case, not just the bug case."""
    from faceless_pipeline.modules.video.assemble import build_background

    clip1 = _make_clip(str(tmp_path / "clip1.mp4"), duration=4.0, color="blue")
    clip2 = _make_clip(str(tmp_path / "clip2.mp4"), duration=4.0, color="green")
    out_path = str(tmp_path / "background.mp4")

    build_background([clip1, clip2], duration_seconds=8.0, out_path=out_path)

    assert _probe_duration(out_path) == pytest.approx(8.0, abs=0.2)
