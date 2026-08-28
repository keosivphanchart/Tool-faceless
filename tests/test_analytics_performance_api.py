"""GET /api/analytics/performance: includes each row's video topic (a
join added for the Analytics page's per-video trend chart, which needs
a human-readable label for the video picker) alongside the raw metrics,
and supports filtering to one video.
"""
from datetime import datetime

from fastapi.testclient import TestClient

from faceless_pipeline.db import get_db
from faceless_pipeline.main import app
from faceless_pipeline.models import Performance, Script, Video, VideoStatus

client = TestClient(app)


def _make_published_video(db_session, topic: str) -> Video:
    script = Script(topic=topic, script={}, style="explainer", length_variant="30s", status="draft")
    db_session.add(script)
    db_session.commit()
    db_session.refresh(script)

    video = Video(script_id=script.id, status=VideoStatus.published)
    db_session.add(video)
    db_session.commit()
    db_session.refresh(video)
    return video


def test_performance_rows_include_video_topic(db_session):
    def _override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db
    try:
        video = _make_published_video(db_session, "Capybara facts")
        db_session.add(Performance(video_id=video.id, platform="youtube", views=100, pulled_at=datetime.utcnow()))
        db_session.commit()

        resp = client.get("/api/analytics/performance")

        assert resp.status_code == 200
        rows = resp.json()
        assert any(r["video_id"] == video.id and r["topic"] == "Capybara facts" for r in rows)
    finally:
        app.dependency_overrides.clear()


def test_performance_filters_by_video_id(db_session):
    def _override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db
    try:
        video_a = _make_published_video(db_session, "Video A")
        video_b = _make_published_video(db_session, "Video B")
        db_session.add(Performance(video_id=video_a.id, platform="youtube", views=10, pulled_at=datetime.utcnow()))
        db_session.add(Performance(video_id=video_b.id, platform="youtube", views=20, pulled_at=datetime.utcnow()))
        db_session.commit()

        resp = client.get("/api/analytics/performance", params={"video_id": video_a.id})

        assert resp.status_code == 200
        rows = resp.json()
        assert all(r["video_id"] == video_a.id for r in rows)
        assert len(rows) == 1
    finally:
        app.dependency_overrides.clear()
