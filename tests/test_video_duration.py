"""Regression test: the final rendered video's duration must match the
*actual* rendered voiceover, not a pre-TTS word-count estimate.

Originally: assemble_pipeline used `len(text.split()) / 2.5` to size the
single background clip, then assemble_video() combined it with the real
audio using ffmpeg's -shortest — so whenever the estimate undershot the
real audio (guaranteed in dry-run mode, where the placeholder audio is a
fixed 3s regardless of script length), the final render would silently
cut the narration off wherever the shorter background stream ended.

The fix now lives one layer down: word-level caption timestamps are
derived directly from the real audio duration (captions.py's
fallback_word_timing calls audio_duration_seconds), and
storyboard.compute_beat_timing() slices those real timestamps per beat —
so background segment durations trace back to real audio by
construction, not a separate estimate that can drift from it. This test
checks the invariant end-to-end: final.mp4's duration must match the
real voiceover's duration, not a word-count guess, even for a script
whose word count would produce a very different estimate.

Requires a real `ffmpeg`; skipped if unavailable.
"""
import shutil
import subprocess
from unittest.mock import patch

import pytest

from faceless_pipeline import config
from faceless_pipeline.modules.scripts.generator import generate_script
from faceless_pipeline.modules.video.captions import audio_duration_seconds
from faceless_pipeline.modules.video.run import assemble_pipeline

pytestmark = pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="requires a real ffmpeg binary")

# A 60-word body gives a word-count estimate of 60/2.5 = 24s, but the
# dry-run placeholder audio is a fixed 3s — the bug this guards against
# would size the background off the 24s estimate while the real audio
# (and therefore the real caption timing) is only ~3s long.
FAKE_SCRIPT_JSON = (
    '{"hook": "h", "promise": "p", '
    '"body": "' + " ".join(["word"] * 60) + '", '
    '"payoff": "pa", "cta": "c"}'
)


class _FakeBlock:
    type = "text"
    text = FAKE_SCRIPT_JSON


class _FakeMessage:
    content = [_FakeBlock()]


def _probe_duration(path: str) -> float:
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", path],
        check=True,
        capture_output=True,
        text=True,
    )
    return float(result.stdout.strip())


def test_final_video_duration_matches_real_audio_not_word_count_estimate(db_session, tmp_path, monkeypatch):
    monkeypatch.setattr(config.settings, "output_dir", str(tmp_path))
    monkeypatch.setattr(config.settings, "pexels_api_key", "")
    monkeypatch.setattr(config.settings, "pixabay_api_key", "")

    with patch("anthropic.Anthropic") as mock_client:
        mock_client.return_value.messages.create.return_value = _FakeMessage()
        script = generate_script(db_session, topic="Duration bug check")

    video = assemble_pipeline(db_session, script.id, dry_run=True)

    word_count_estimate = 60 / 2.5
    real_audio_duration = audio_duration_seconds(video.audio_path)
    final_duration = _probe_duration(video.file_path)

    assert real_audio_duration < word_count_estimate, (
        "this scenario (dry-run) should show real audio shorter than the "
        "old word-count estimate; if this ever flips, it no longer "
        "exercises the truncation bug this test guards against"
    )
    assert final_duration == pytest.approx(real_audio_duration, abs=0.5)
