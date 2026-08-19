"""POST /api/videos/batch-schedule (content calendar: spread N pending
videos across future slots) and POST /api/pipeline/trigger/full-cycle
(trend finder + auto-generate in one call, for an external cron/n8n
hook).
"""
from datetime import datetime, timedelta
from unittest.mock import patch

from fastapi.testclient import TestClient

from faceless_pipeline.db import get_db
from faceless_pipeline.main import app
from faceless_pipeline.models import Script, Trend, Video, VideoStatus

client = TestClient(app)


def _make_pending_video(db_session, topic: str) -> Video:
    script = Script(topic=topic, script={"hook": "h", "promise": "p", "body": "b", "payoff": "pa", "cta": "c"})
    db_session.add(script)
    db_session.commit()
    db_session.refresh(script)

    video = Video(script_id=script.id, status=VideoStatus.pending)
    db_session.add(video)
    db_session.commit()
    db_session.refresh(video)
    return video


def test_batch_schedule_spreads_videos_across_interval_slots(db_session):
    def _override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db
    try:
        v1 = _make_pending_video(db_session, "Batch topic 1")
        v2 = _make_pending_video(db_session, "Batch topic 2")
        start = (datetime.utcnow() + timedelta(hours=1)).isoformat() + "Z"

        with patch("faceless_pipeline.modules.publisher.run.publish_video"):
            resp = client.post(
                "/api/videos/batch-schedule",
                json={"video_ids": [v1.id, v2.id], "start_at": start, "interval_hours": 24},
            )

        assert resp.status_code == 200, resp.text
        scheduled = resp.json()["scheduled"]
        assert len(scheduled) == 2
        t0 = datetime.fromisoformat(scheduled[0]["scheduled_for"])
        t1 = datetime.fromisoformat(scheduled[1]["scheduled_for"])
        assert (t1 - t0) == timedelta(hours=24)

        db_session.refresh(v1)
        db_session.refresh(v2)
        assert v1.status == VideoStatus.approved
        assert v2.status == VideoStatus.approved
    finally:
        app.dependency_overrides.clear()


def test_batch_schedule_skips_non_pending_videos(db_session):
    def _override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db
    try:
        video = _make_pending_video(db_session, "Already approved")
        video.status = VideoStatus.approved
        db_session.commit()
        start = (datetime.utcnow() + timedelta(hours=1)).isoformat() + "Z"

        resp = client.post("/api/videos/batch-schedule", json={"video_ids": [video.id], "start_at": start})

        assert resp.status_code == 200
        assert resp.json()["scheduled"] == []
    finally:
        app.dependency_overrides.clear()


def test_batch_schedule_rejects_empty_video_ids(db_session):
    def _override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db
    try:
        start = (datetime.utcnow() + timedelta(hours=1)).isoformat() + "Z"
        resp = client.post("/api/videos/batch-schedule", json={"video_ids": [], "start_at": start})
        assert resp.status_code == 400
    finally:
        app.dependency_overrides.clear()


def test_batch_schedule_rejects_a_start_time_in_the_past(db_session):
    def _override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db
    try:
        video = _make_pending_video(db_session, "Past start test")
        past = (datetime.utcnow() - timedelta(hours=1)).isoformat() + "Z"
        resp = client.post("/api/videos/batch-schedule", json={"video_ids": [video.id], "start_at": past})
        assert resp.status_code == 400
    finally:
        app.dependency_overrides.clear()


def test_full_cycle_runs_trend_finder_then_auto_generates(db_session):
    def _override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db
    try:
        with patch("faceless_pipeline.modules.trends.run.run_trend_finder") as mock_trends, patch(
            "faceless_pipeline.modules.automation.run.auto_generate_from_trends"
        ) as mock_generate:
            mock_trends.return_value = [Trend(topic="x", normalized_topic="x", source="google_trends", score=1)]
            mock_generate.return_value = []

            resp = client.post("/api/pipeline/trigger/full-cycle")

        assert resp.status_code == 200
        assert resp.json() == {"triggered": "full-cycle"}
        mock_trends.assert_called_once()
        mock_generate.assert_called_once()
    finally:
        app.dependency_overrides.clear()


def test_full_cycle_passes_through_count_and_min_score_overrides(db_session):
    def _override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db
    try:
        with patch("faceless_pipeline.modules.trends.run.run_trend_finder", return_value=[]), patch(
            "faceless_pipeline.modules.automation.run.auto_generate_from_trends"
        ) as mock_generate:
            mock_generate.return_value = []
            client.post("/api/pipeline/trigger/full-cycle", params={"count": 3, "min_score": 42.0})

        _, kwargs = mock_generate.call_args
        assert kwargs["count"] == 3
        assert kwargs["min_score"] == 42.0
    finally:
        app.dependency_overrides.clear()
