"""Regression test: normalize_loudness()'s output must stay in a plain
PCM wav format that Python's stdlib `wave` module can parse.

Found by actually running the pipeline against real ffmpeg (not just the
"ffmpeg unavailable" degraded path every other test exercises): ffmpeg's
loudnorm filter oversamples internally for its true-peak (TP) analysis,
and without an explicit output sample rate, left the output at 192kHz
(from a 24kHz input). That flips the wav header to
WAVE_FORMAT_EXTENSIBLE, which `wave.open()` cannot read — silently
breaking video/captions.audio_duration_seconds(), which falls back to a
hardcoded 30s default. That default directly feeds video/run.py's
background-clip duration (the fix for a *different* bug: background
duration undershooting the real narration and getting cut off by
ffmpeg's -shortest) — so this bug was quietly defeating that fix every
time loudnorm actually ran.

Requires a real `ffmpeg` binary; skipped if unavailable so the rest of
the suite still runs in environments without it.
"""
import shutil
import subprocess
import wave

import pytest

pytestmark = pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="requires a real ffmpeg binary")


@pytest.fixture()
def input_wav(tmp_path):
    """A short 24kHz tone, matching Kokoro's typical output rate — the
    same rate that triggered the 192kHz-oversampling bug."""
    path = tmp_path / "in.wav"
    subprocess.run(
        [
            "ffmpeg", "-y", "-f", "lavfi", "-i", "sine=frequency=440:duration=2:sample_rate=24000",
            "-c:a", "pcm_s16le", str(path),
        ],
        check=True,
        capture_output=True,
    )
    return str(path)


def test_normalized_output_is_readable_by_stdlib_wave_module(input_wav, tmp_path):
    from faceless_pipeline.modules.voice.normalize import normalize_loudness

    out_path = str(tmp_path / "out.wav")
    normalize_loudness(input_wav, out_path)

    with wave.open(out_path, "rb") as f:
        duration = f.getnframes() / f.getframerate()

    assert duration == pytest.approx(2.0, abs=0.1)


def test_normalized_output_is_not_left_at_an_oversampled_rate(input_wav, tmp_path):
    from faceless_pipeline.modules.voice.normalize import normalize_loudness

    out_path = str(tmp_path / "out.wav")
    normalize_loudness(input_wav, out_path)

    with wave.open(out_path, "rb") as f:
        rate = f.getframerate()

    assert rate == 48000
