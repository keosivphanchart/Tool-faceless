"""GET /api/videos/needs-attention (an approved video whose scheduled
publish is well overdue - the scheduler retries a failed publish
forever, silently, so this is the only place that becomes visible) and
PATCH /api/videos/{id}/script (a light text-only edit, letting a
reviewer fix a hook/CTA without spending an LLM call on a full
"Regenerate script").
"""
from datetime import datetime, timedelta

from fastapi.testclient import TestClient

from faceless_pipeline.db import get_db
from faceless_pipeline.main import app
from faceless_pipeline.models import Script, Video, VideoStatus

client = TestClient(app)


def _make_video(db_session, topic: str, status=VideoStatus.pending, scheduled_for=None) -> Video:
    script = Script(topic=topic, script={"hook": "h", "promise": "p", "body": "b", "payoff": "pa", "cta": "c"})
    db_session.add(script)
    db_session.commit()
    db_session.refresh(script)

    video = Video(script_id=script.id, status=status, scheduled_for=scheduled_for)
    db_session.add(video)
    db_session.commit()
    db_session.refresh(video)
    return video


def _with_db(db_session):
    def _override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db
    return app.dependency_overrides.clear


def test_needs_attention_lists_a_video_overdue_past_the_threshold(db_session):
    clear = _with_db(db_session)
    try:
        overdue = _make_video(
            db_session, "Stuck video", status=VideoStatus.approved, scheduled_for=datetime.utcnow() - timedelta(minutes=30)
        )

        resp = client.get("/api/videos/needs-attention")

        assert resp.status_code == 200
        ids = [v["id"] for v in resp.json()]
        assert overdue.id in ids
    finally:
        clear()


def test_needs_attention_excludes_a_video_just_barely_due(db_session):
    """A video whose scheduled_for passed a minute ago is just waiting
    for the next 60s dispatcher tick, not stuck - shouldn't be flagged."""
    clear = _with_db(db_session)
    try:
        _make_video(db_session, "Fine video", status=VideoStatus.approved, scheduled_for=datetime.utcnow() - timedelta(minutes=1))

        resp = client.get("/api/videos/needs-attention")

        assert resp.status_code == 200
        assert resp.json() == []
    finally:
        clear()


def test_needs_attention_excludes_unscheduled_approved_videos(db_session):
    """An approved video with no scheduled_for is just waiting in the
    recurring-slot queue - normal, not stuck."""
    clear = _with_db(db_session)
    try:
        _make_video(db_session, "Waiting in queue", status=VideoStatus.approved, scheduled_for=None)

        resp = client.get("/api/videos/needs-attention")

        assert resp.status_code == 200
        assert resp.json() == []
    finally:
        clear()


def test_needs_attention_excludes_pending_and_published_videos(db_session):
    clear = _with_db(db_session)
    try:
        _make_video(db_session, "Pending", status=VideoStatus.pending)
        _make_video(db_session, "Published", status=VideoStatus.published, scheduled_for=datetime.utcnow() - timedelta(hours=1))

        resp = client.get("/api/videos/needs-attention")

        assert resp.status_code == 200
        assert resp.json() == []
    finally:
        clear()


def test_edit_script_updates_only_the_fields_given(db_session):
    clear = _with_db(db_session)
    try:
        video = _make_video(db_session, "Editable")

        resp = client.patch(f"/api/videos/{video.id}/script", json={"hook": "New hook", "cta": "New CTA"})

        assert resp.status_code == 200
        body = resp.json()
        assert body["script"]["text"]["hook"] == "New hook"
        assert body["script"]["text"]["cta"] == "New CTA"
        assert body["script"]["text"]["body"] == "b"  # untouched
    finally:
        clear()


def test_edit_script_missing_video_returns_404(db_session):
    clear = _with_db(db_session)
    try:
        resp = client.patch("/api/videos/999999/script", json={"hook": "x"})
        assert resp.status_code == 404
    finally:
        clear()
