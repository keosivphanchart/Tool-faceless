"""Zero-API-key usability: without Pexels/Pixabay keys, video assembly
used to just give up (final_path=None) — nothing in this project could
produce a real, watchable video without first signing up for a stock
footage API. generate_procedural_background() renders an animated
gradient using only ffmpeg's own built-in filters (no network call, no
API key, no model download), and assemble_pipeline() now falls back to
it automatically whenever fetch_background_clips() comes back empty.

Requires a real `ffmpeg`; skipped if unavailable.
"""
import shutil
import subprocess
from unittest.mock import patch

import pytest

from faceless_pipeline import config
from faceless_pipeline.modules.scripts.generator import generate_script
from faceless_pipeline.modules.video.procedural_background import _pick_for_topic, generate_procedural_background
from faceless_pipeline.modules.video.run import assemble_pipeline

pytestmark = pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="requires a real ffmpeg binary")

FAKE_SCRIPT_JSON = '{"hook": "h", "promise": "p", "body": "body text here", "payoff": "pa", "cta": "c"}'


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


def test_generates_a_real_video_of_the_requested_duration(tmp_path):
    out_path = str(tmp_path / "bg.mp4")
    generate_procedural_background(4.0, out_path, topic="deep sea facts")

    assert _probe_duration(out_path) == pytest.approx(4.0, abs=0.2)


def test_same_topic_picks_the_same_look_every_time():
    assert _pick_for_topic("deep sea facts") == _pick_for_topic("deep sea facts")


def test_different_topics_usually_pick_different_looks():
    picks = {_pick_for_topic(f"topic {i}") for i in range(10)}
    assert len(picks) > 1


def test_assemble_pipeline_renders_a_real_video_with_zero_stock_footage_keys(db_session, tmp_path, monkeypatch):
    """The end-to-end behavior that actually matters: no PEXELS_API_KEY,
    no PIXABAY_API_KEY, no stock footage - assemble_pipeline() must still
    produce a real, playable final.mp4, not give up."""
    monkeypatch.setattr(config.settings, "output_dir", str(tmp_path))
    monkeypatch.setattr(config.settings, "pexels_api_key", "")
    monkeypatch.setattr(config.settings, "pixabay_api_key", "")

    with patch("anthropic.Anthropic") as mock_client:
        mock_client.return_value.messages.create.return_value = _FakeMessage()
        script = generate_script(db_session, topic="Zero key test topic")

    video = assemble_pipeline(db_session, script.id, dry_run=True)

    assert video.file_path is not None, "should render a real video, not give up, when no stock footage keys are set"
    duration = _probe_duration(video.file_path)
    assert duration > 0
