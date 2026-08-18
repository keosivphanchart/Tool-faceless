"""Regression tests for two bugs found in Module 5's regenerate flow:

1. Two assemble_pipeline() runs for the same script (i.e. "regenerate
   video") used to share an output directory keyed only by script_id, so
   the second run silently overwrote the first run's audio/video files on
   disk while the first Video row's paths kept pointing at that same,
   now-different, content.
2. "regenerate script" created a new Script row but never re-assembled a
   video for it, so the rewrite never produced anything new to review.
3. assemble_pipeline/generate_voiceover each opened their own DB session
   instead of taking the caller's, so calling them from inside an
   already-open request session (exactly what the regenerate endpoints do)
   raced two sessions against the same connection and corrupted the
   transaction — reproduced via the real /api/videos/{id}/regenerate route,
   not just direct calls, before both functions were changed to accept
   `db` as a parameter.
"""
from unittest.mock import patch

from faceless_pipeline.models import Video, VideoStatus
from faceless_pipeline.modules.review.api import RegenerateRequest, regenerate_video
from faceless_pipeline.modules.scripts.generator import generate_script
from faceless_pipeline.modules.video.run import assemble_pipeline

FAKE_SCRIPT_JSON = (
    '{"hook": "h", "promise": "p", "body": "body text here", "payoff": "pa", "cta": "c"}'
)


class _FakeBlock:
    type = "text"
    text = FAKE_SCRIPT_JSON


class _FakeMessage:
    content = [_FakeBlock()]


def _generate(db):
    with patch("anthropic.Anthropic") as mock_client:
        mock_client.return_value.messages.create.return_value = _FakeMessage()
        return generate_script(db, topic="Regen bug check")


def test_repeated_assembly_for_same_script_does_not_collide(db_session, tmp_path, monkeypatch):
    from faceless_pipeline import config

    monkeypatch.setattr(config.settings, "output_dir", str(tmp_path))

    script = _generate(db_session)

    v1 = assemble_pipeline(db_session, script.id, dry_run=True)
    v2 = assemble_pipeline(db_session, script.id, dry_run=True)

    assert v1.id != v2.id
    assert v1.audio_path != v2.audio_path
    import os

    assert os.path.exists(v1.audio_path), "first run's audio must survive the second run"
    assert os.path.exists(v2.audio_path)


def test_regenerate_script_produces_a_new_pending_video(db_session, tmp_path, monkeypatch):
    from faceless_pipeline import config

    monkeypatch.setattr(config.settings, "output_dir", str(tmp_path))

    script = _generate(db_session)
    video = assemble_pipeline(db_session, script.id, dry_run=True)

    with patch("anthropic.Anthropic") as mock_client:
        mock_client.return_value.messages.create.return_value = _FakeMessage()
        result = regenerate_video(video.id, RegenerateRequest(target="script", note="punchier hook"), db=db_session)

    assert "new_video_id" in result
    new_video = db_session.get(Video, result["new_video_id"])
    assert new_video.status == VideoStatus.pending
    assert new_video.script_id == result["new_script_id"]

    pending = db_session.query(Video).filter(Video.status == VideoStatus.pending).all()
    assert [v.id for v in pending] == [new_video.id]
