"""Regression test: every ffmpeg subprocess.run call must have a timeout.

Module 4's ffmpeg calls (assemble.py's _run, used by build_background /
assemble_video / generate_thumbnail, and voice/normalize.py's
normalize_loudness) used to call subprocess.run() with no timeout. A
genuinely hung ffmpeg process — corrupt input, a filter graph that never
terminates — would then block whichever thread called it forever. Since
assemble_pipeline() is invoked from FastAPI BackgroundTasks, that's a
server worker thread that never comes back, not just a slow CLI call.
"""
import stat
import time

import pytest

from faceless_pipeline.config import settings


@pytest.fixture()
def slow_ffmpeg_binary(tmp_path):
    """A fake 'ffmpeg' that sleeps far longer than any test timeout."""
    script = tmp_path / "slow_ffmpeg.sh"
    script.write_text("#!/bin/sh\nsleep 30\n")
    script.chmod(script.stat().st_mode | stat.S_IEXEC)

    original_binary = settings.ffmpeg_binary
    original_timeout = settings.ffmpeg_timeout_seconds
    settings.ffmpeg_binary = str(script)
    settings.ffmpeg_timeout_seconds = 1
    yield
    settings.ffmpeg_binary = original_binary
    settings.ffmpeg_timeout_seconds = original_timeout


def test_generate_thumbnail_times_out_instead_of_hanging(slow_ffmpeg_binary, tmp_path):
    from faceless_pipeline.modules.video.assemble import generate_thumbnail

    start = time.perf_counter()
    with pytest.raises(RuntimeError, match="timed out"):
        generate_thumbnail(str(tmp_path / "in.mp4"), str(tmp_path / "out.jpg"))
    assert time.perf_counter() - start < 10, "timeout was not enforced — call blocked far longer than configured"


def test_normalize_loudness_times_out_instead_of_hanging(slow_ffmpeg_binary, tmp_path):
    from faceless_pipeline.modules.voice.normalize import normalize_loudness

    start = time.perf_counter()
    with pytest.raises(RuntimeError, match="timed out"):
        normalize_loudness(str(tmp_path / "in.wav"), str(tmp_path / "out.wav"))
    assert time.perf_counter() - start < 10, "timeout was not enforced — call blocked far longer than configured"
