"""Regression test: build_background() must be sized to the *actual*
rendered voiceover duration, not a pre-TTS word-count estimate.

Previously assemble_pipeline used `len(text.split()) / 2.5` to size the
background clip, then assemble_video() combined it with the real audio
using ffmpeg's -shortest — so whenever the estimate undershot the real
audio (guaranteed in dry-run mode, where the placeholder audio is a fixed
3s regardless of script length), the final render would silently cut the
narration off wherever the shorter background stream ended.
"""
from unittest.mock import patch

from faceless_pipeline.modules.scripts.generator import generate_script
from faceless_pipeline.modules.video.captions import audio_duration_seconds
from faceless_pipeline.modules.video.run import assemble_pipeline

FAKE_SCRIPT_JSON = (
    '{"hook": "h", "promise": "p", '
    '"body": "' + " ".join(["word"] * 60) + '", '  # long body -> large word-count estimate
    '"payoff": "pa", "cta": "c"}'
)


class _FakeBlock:
    type = "text"
    text = FAKE_SCRIPT_JSON


class _FakeMessage:
    content = [_FakeBlock()]


def test_background_duration_matches_real_audio_not_word_count_estimate(db_session, tmp_path, monkeypatch):
    from faceless_pipeline import config

    monkeypatch.setattr(config.settings, "output_dir", str(tmp_path))

    with patch("anthropic.Anthropic") as mock_client:
        mock_client.return_value.messages.create.return_value = _FakeMessage()
        script = generate_script(db_session, topic="Duration bug check")

    captured = {}

    def _fake_build_background(clip_paths, duration_seconds, out_path):
        captured["duration"] = duration_seconds
        return out_path

    # A 60-word body gives a word-count estimate of 60/2.5 = 24s, but the
    # dry-run placeholder audio is a fixed 3s — the bug would pass 24s to
    # build_background while the real audio is only 3s long.
    word_count_estimate = 60 / 2.5

    with patch("faceless_pipeline.modules.video.run.fetch_background_clips", return_value=["/fake/clip.mp4"]), \
         patch("faceless_pipeline.modules.video.run.build_background", side_effect=_fake_build_background), \
         patch("faceless_pipeline.modules.video.run.assemble_video"), \
         patch("faceless_pipeline.modules.video.run.generate_thumbnail"):
        video = assemble_pipeline(db_session, script.id, dry_run=True)

    real_audio_duration = audio_duration_seconds(video.audio_path)

    assert captured["duration"] == real_audio_duration
    assert captured["duration"] != word_count_estimate
    assert captured["duration"] < word_count_estimate, (
        "this specific scenario (dry-run) should show the real audio "
        "shorter than the old estimate; if this ever flips, the bug this "
        "test guards against would have caused truncation instead"
    )
