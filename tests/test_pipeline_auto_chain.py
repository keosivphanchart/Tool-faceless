"""Regression test: generating a script through the pipeline trigger must
automatically produce a reviewable video, not just sit there.

Per the spec ("a script gets written, voice and video get assembled
automatically, a human approves"), video assembly is not a separate
manual step a human has to remember to trigger once a topic is picked -
trigger_script_generation() used to call generate_script() and stop,
leaving the script with no way to become a video short of running a CLI
command by hand. Fixed by chaining assemble_pipeline() after a
successful generation, recording both stages on the pipeline status.
"""
from unittest.mock import patch

from fastapi.testclient import TestClient

from faceless_pipeline.db import get_db
from faceless_pipeline.main import app
from faceless_pipeline.models import Video, VideoStatus

FAKE_SCRIPT_JSON = '{"hook": "h", "promise": "p", "body": "body text here", "payoff": "pa", "cta": "c"}'


class _FakeBlock:
    type = "text"
    text = FAKE_SCRIPT_JSON


class _FakeMessage:
    content = [_FakeBlock()]


def test_script_trigger_automatically_produces_a_pending_video(db_session):
    def _override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db
    client = TestClient(app)

    try:
        with patch("anthropic.Anthropic") as mock_client:
            mock_client.return_value.messages.create.return_value = _FakeMessage()
            resp = client.post("/api/pipeline/trigger/script", params={"topic": "Auto chain test topic"})
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 200

    pending = db_session.query(Video).filter(Video.status == VideoStatus.pending).all()
    assert len(pending) == 1, "script generation must automatically chain into video assembly"

    stages = client.get("/api/pipeline/status").json()["stages"]
    stage_names = {s["stage"] for s in stages}
    assert {"script", "video"} <= stage_names
    assert all(s["status"] == "success" for s in stages if s["stage"] in ("script", "video"))
