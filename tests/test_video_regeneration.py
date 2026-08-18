"""Regression tests for four bugs found in Module 5's regenerate flow:

1. Two assemble_pipeline() runs for the same script (i.e. "regenerate
   video") used to share an output directory keyed only by script_id, so
   the second run silently overwrote the first run's audio/video files on
   disk while the first Video row's paths kept pointing at that same,
   now-different, content.
2. "regenerate script" created a new Script row but never re-assembled a
   video for it, so the rewrite never produced anything new to review.
3. assemble_pipeline/generate_voiceover each opened their own DB session
   instead of taking the caller's, so calling them from inside an
   already-open request session (exactly what the regenerate endpoint
   does) raced two sessions against the same connection and corrupted the
   transaction — reproduced via the real /api/videos/{id}/regenerate
   route, not just direct calls, before both functions were changed to
   accept `db` as a parameter.
4. regenerate_video ran the rewrite (a Claude API call) and reassembly
   (TTS + ffmpeg) synchronously inside the request handler, so the HTTP
   call blocked for however long those took - anywhere from seconds to
   minutes - instead of backgrounding like approve_video already did for
   publishing. Now runs as a background task; the endpoint itself is
   tested via TestClient below, since a background task only actually
   executes as part of the real request/response lifecycle.
"""
import os
from unittest.mock import patch

from fastapi.testclient import TestClient

from faceless_pipeline.db import get_db
from faceless_pipeline.main import app
from faceless_pipeline.models import Video, VideoStatus
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
    assert os.path.exists(v1.audio_path), "first run's audio must survive the second run"
    assert os.path.exists(v2.audio_path)


def test_regenerate_script_produces_a_new_pending_video(db_session, tmp_path, monkeypatch):
    """Exercises the real HTTP endpoint (not a direct function call), since
    the fix for bug #4 moved the rewrite+reassembly into a BackgroundTasks
    job that only runs as part of an actual request/response cycle."""
    from faceless_pipeline import config

    monkeypatch.setattr(config.settings, "output_dir", str(tmp_path))

    script = _generate(db_session)
    video = assemble_pipeline(db_session, script.id, dry_run=True)

    def _override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db
    client = TestClient(app)

    try:
        with patch("anthropic.Anthropic") as mock_client:
            mock_client.return_value.messages.create.return_value = _FakeMessage()
            resp = client.post(
                f"/api/videos/{video.id}/regenerate",
                json={"target": "script", "note": "punchier hook"},
            )
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 200
    body = resp.json()
    assert body["regenerating"] == "script"
    assert body["status"] == "queued"

    db_session.refresh(video)
    assert video.status == VideoStatus.rejected

    pending = db_session.query(Video).filter(Video.status == VideoStatus.pending).all()
    assert len(pending) == 1
    new_video = pending[0]
    assert new_video.id != video.id
    assert new_video.script_id != script.id
