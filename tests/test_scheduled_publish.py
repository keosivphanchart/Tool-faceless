"""Scheduling a video's publish: publish_video(scheduled_for=...) used to
just store the timestamp and return - approving a video with a future
schedule was a dead end, since nothing ever came back to actually
publish it once that time arrived. Covers the full loop: the approve
endpoint accepting a schedule, the scheduled list/unschedule endpoints,
and the dispatcher that actually publishes due videos.
"""
from datetime import datetime, timedelta
from unittest.mock import patch

from fastapi.testclient import TestClient

from faceless_pipeline.db import get_db
from faceless_pipeline.main import app
from faceless_pipeline.models import Script, Video, VideoStatus
from faceless_pipeline.modules.publisher.scheduler import dispatch_due_scheduled_publishes

client = TestClient(app)


def _make_pending_video(db_session, tmp_path, topic: str = "Scheduling test topic") -> Video:
    script = Script(topic=topic, script={"hook": "h", "promise": "p", "body": "b", "payoff": "pa", "cta": "c"})
    db_session.add(script)
    db_session.commit()
    db_session.refresh(script)

    fake_video_file = tmp_path / f"{topic.replace(' ', '_')}.mp4"
    fake_video_file.write_bytes(b"not a real mp4, just needs to exist")

    video = Video(script_id=script.id, status=VideoStatus.pending, file_path=str(fake_video_file))
    db_session.add(video)
    db_session.commit()
    db_session.refresh(video)
    return video


def test_approve_with_scheduled_for_stores_it_without_publishing_immediately(db_session, tmp_path):
    def _override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db
    try:
        video = _make_pending_video(db_session, tmp_path)
        future = (datetime.utcnow() + timedelta(hours=1)).isoformat()

        with patch("faceless_pipeline.modules.publisher.youtube.upload_video") as mock_upload:
            resp = client.post(f"/api/videos/{video.id}/approve", json={"scheduled_for": future})
            assert resp.status_code == 200
            mock_upload.assert_not_called()

        db_session.refresh(video)
        assert video.status == VideoStatus.approved
        assert video.scheduled_for is not None
        assert video.platform_ids == {}
    finally:
        app.dependency_overrides.clear()


def test_approve_accepts_a_timezone_aware_iso_string_like_the_real_browser_sends(db_session, tmp_path):
    """Regression: the dashboard sends `new Date(...).toISOString()`,
    which is always timezone-aware (a trailing "Z"), not the naive
    `datetime.isoformat()` string a Python-side test would produce by
    default. Comparing that aware value against datetime.utcnow() (naive)
    raised "TypeError: can't compare offset-naive and offset-aware
    datetimes" - a 500 caught only by driving the real endpoint with a
    real tz-aware string, exactly like this test does.
    """

    def _override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db
    try:
        video = _make_pending_video(db_session, tmp_path)
        # Explicitly tz-aware with a "Z" suffix, matching JS's toISOString().
        future_aware = (datetime.utcnow() + timedelta(hours=1)).isoformat() + "Z"

        resp = client.post(f"/api/videos/{video.id}/approve", json={"scheduled_for": future_aware})

        assert resp.status_code == 200, resp.text
        db_session.refresh(video)
        assert video.scheduled_for is not None
        assert video.scheduled_for.tzinfo is None  # stored as naive UTC, consistent with every other datetime column
    finally:
        app.dependency_overrides.clear()


def test_approve_rejects_a_schedule_in_the_past(db_session, tmp_path):
    def _override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db
    try:
        video = _make_pending_video(db_session, tmp_path)
        past = (datetime.utcnow() - timedelta(hours=1)).isoformat()

        resp = client.post(f"/api/videos/{video.id}/approve", json={"scheduled_for": past})

        assert resp.status_code == 400
    finally:
        app.dependency_overrides.clear()


def test_scheduled_video_appears_in_upcoming_list(db_session, tmp_path):
    def _override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db
    try:
        video = _make_pending_video(db_session, tmp_path, "Upcoming list test")
        future = datetime.utcnow() + timedelta(hours=2)
        video.status = VideoStatus.approved
        video.scheduled_for = future
        db_session.commit()

        resp = client.get("/api/videos/scheduled/upcoming")

        assert resp.status_code == 200
        ids = [v["id"] for v in resp.json()]
        assert video.id in ids
    finally:
        app.dependency_overrides.clear()


def test_unschedule_clears_the_timestamp_but_keeps_approved_status(db_session, tmp_path):
    def _override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db
    try:
        video = _make_pending_video(db_session, tmp_path, "Unschedule test")
        video.status = VideoStatus.approved
        video.scheduled_for = datetime.utcnow() + timedelta(hours=3)
        db_session.commit()

        resp = client.post(f"/api/videos/{video.id}/unschedule")

        assert resp.status_code == 200
        assert resp.json()["scheduled_for"] is None
        db_session.refresh(video)
        assert video.scheduled_for is None
        assert video.status == VideoStatus.approved
    finally:
        app.dependency_overrides.clear()


def test_unschedule_a_video_with_no_schedule_is_rejected(db_session, tmp_path):
    def _override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db
    try:
        video = _make_pending_video(db_session, tmp_path, "No schedule test")
        video.status = VideoStatus.approved
        db_session.commit()

        resp = client.post(f"/api/videos/{video.id}/unschedule")

        assert resp.status_code == 400
    finally:
        app.dependency_overrides.clear()


def test_dispatcher_publishes_a_due_video(db_session, tmp_path):
    with patch("faceless_pipeline.modules.publisher.scheduler.SessionLocal", return_value=db_session), patch.object(
        db_session, "close", lambda: None
    ):
        video = _make_pending_video(db_session, tmp_path, "Due dispatch test")
        video.status = VideoStatus.approved
        video.scheduled_for = datetime.utcnow() - timedelta(minutes=1)  # already due
        db_session.commit()

        with patch("faceless_pipeline.modules.publisher.run.youtube_upload", return_value="yt-due-123"):
            attempted = dispatch_due_scheduled_publishes()

        assert attempted == 1
        db_session.refresh(video)
        assert video.status == VideoStatus.published
        assert video.platform_ids.get("youtube") == "yt-due-123"


def test_dispatcher_ignores_videos_not_yet_due(db_session, tmp_path):
    with patch("faceless_pipeline.modules.publisher.scheduler.SessionLocal", return_value=db_session), patch.object(
        db_session, "close", lambda: None
    ):
        video = _make_pending_video(db_session, tmp_path, "Not due yet test")
        video.status = VideoStatus.approved
        video.scheduled_for = datetime.utcnow() + timedelta(hours=5)  # not due
        db_session.commit()

        with patch("faceless_pipeline.modules.publisher.run.youtube_upload") as mock_upload:
            attempted = dispatch_due_scheduled_publishes()
            mock_upload.assert_not_called()

        assert attempted == 0
        db_session.refresh(video)
        assert video.status == VideoStatus.approved


def test_dispatcher_retries_a_video_that_failed_to_publish(db_session, tmp_path):
    with patch("faceless_pipeline.modules.publisher.scheduler.SessionLocal", return_value=db_session), patch.object(
        db_session, "close", lambda: None
    ):
        video = _make_pending_video(db_session, tmp_path, "Retry test")
        video.status = VideoStatus.approved
        video.scheduled_for = datetime.utcnow() - timedelta(minutes=1)
        db_session.commit()

        with patch("faceless_pipeline.modules.publisher.run.youtube_upload", side_effect=RuntimeError("network blip")):
            attempted = dispatch_due_scheduled_publishes()

        assert attempted == 1
        db_session.refresh(video)
        # Still approved, still scheduled in the past -> the next tick will retry it.
        assert video.status == VideoStatus.approved
        assert video.scheduled_for is not None
