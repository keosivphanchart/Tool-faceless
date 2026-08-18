"""Background jobs (auto-publish after approval, regenerate-on-rejection)
used to only log exceptions server-side on failure - nothing surfaced it
anywhere a reviewer would actually see, short of knowing to check
Pipeline Status and read a status table. record_run() now also appends to
a bounded, pollable event log (GET /api/pipeline/events?after=<id>) that
the dashboard's global toast polls, so a failure shows up no matter which
page is open when it happens.

These tests exercise the real endpoints through TestClient (not the
in-process record_run() function directly), so they prove the actual
review-checkpoint code paths append events on both success and failure,
not just that record_run() itself works.
"""
from types import SimpleNamespace
from unittest.mock import patch

from fastapi.testclient import TestClient

from faceless_pipeline.db import get_db
from faceless_pipeline.main import app
from faceless_pipeline.models import Script, Video, VideoStatus

client = TestClient(app)


def _make_pending_video(db_session) -> Video:
    script = Script(topic="Event test topic", script={"hook": "h", "promise": "p", "body": "b", "payoff": "pa", "cta": "c"})
    db_session.add(script)
    db_session.commit()
    db_session.refresh(script)

    video = Video(script_id=script.id, status=VideoStatus.pending)
    db_session.add(video)
    db_session.commit()
    db_session.refresh(video)
    return video


def _latest_event_id(client) -> int:
    events = client.get("/api/pipeline/events", params={"after": 0}).json()["events"]
    return max((e["id"] for e in events), default=0)


def test_events_endpoint_only_returns_events_after_the_given_id(db_session):
    def _override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db
    try:
        baseline = _latest_event_id(client)

        video = _make_pending_video(db_session)
        with patch("faceless_pipeline.modules.publisher.run.publish_video") as mock_publish:
            mock_publish.return_value = SimpleNamespace(platform_ids={"youtube": "yt123"})
            client.post(f"/api/videos/{video.id}/approve")

        after_baseline = client.get("/api/pipeline/events", params={"after": baseline}).json()["events"]
        assert any(e["stage"] == "publish" for e in after_baseline)

        newest_id = max(e["id"] for e in after_baseline)
        nothing_new = client.get("/api/pipeline/events", params={"after": newest_id}).json()["events"]
        assert nothing_new == []
    finally:
        app.dependency_overrides.clear()


def test_approve_publish_failure_is_recorded_as_an_error_event(db_session):
    def _override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db
    try:
        baseline = _latest_event_id(client)
        video = _make_pending_video(db_session)

        with patch("faceless_pipeline.modules.publisher.run.publish_video") as mock_publish:
            mock_publish.side_effect = RuntimeError("YouTube OAuth not set up")
            client.post(f"/api/videos/{video.id}/approve")

        events = client.get("/api/pipeline/events", params={"after": baseline}).json()["events"]
        publish_events = [e for e in events if e["stage"] == "publish"]
        assert len(publish_events) == 1
        assert publish_events[0]["status"] == "error"
        assert "YouTube OAuth not set up" in publish_events[0]["detail"]
        assert str(video.id) in publish_events[0]["detail"]
    finally:
        app.dependency_overrides.clear()


def test_approve_publish_with_no_platform_accepted_is_recorded_as_error(db_session):
    """publish_video() itself swallows per-platform failures (so one bad
    platform doesn't block the others) and just leaves platform_ids
    empty - that must still surface as a dashboard-visible failure, not
    silently look like a no-op success."""

    def _override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db
    try:
        baseline = _latest_event_id(client)
        video = _make_pending_video(db_session)

        with patch("faceless_pipeline.modules.publisher.run.publish_video") as mock_publish:
            mock_publish.return_value = SimpleNamespace(platform_ids={})
            client.post(f"/api/videos/{video.id}/approve")

        events = client.get("/api/pipeline/events", params={"after": baseline}).json()["events"]
        publish_events = [e for e in events if e["stage"] == "publish"]
        assert len(publish_events) == 1
        assert publish_events[0]["status"] == "error"
    finally:
        app.dependency_overrides.clear()


def test_regenerate_failure_is_recorded_as_an_error_event(db_session):
    def _override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db
    try:
        baseline = _latest_event_id(client)
        video = _make_pending_video(db_session)

        with patch("faceless_pipeline.modules.video.run.assemble_pipeline") as mock_assemble:
            mock_assemble.side_effect = RuntimeError("ffmpeg not installed")
            client.post(f"/api/videos/{video.id}/regenerate", json={"target": "video", "note": "too dark"})

        events = client.get("/api/pipeline/events", params={"after": baseline}).json()["events"]
        regen_events = [e for e in events if e["stage"] == "regenerate"]
        assert len(regen_events) == 1
        assert regen_events[0]["status"] == "error"
        assert "ffmpeg not installed" in regen_events[0]["detail"]
    finally:
        app.dependency_overrides.clear()
