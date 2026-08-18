from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import app
from app.models import Script, Video, VideoStatus

client = TestClient(app)


def test_review_queue_approve_reject_flow(db_session, monkeypatch):
    # Point the app's dependency-injected session at the same in-memory db
    from app.db import get_db

    def _override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db

    script = Script(topic="Test topic", script={"hook": "h", "promise": "p", "body": "b", "payoff": "pa", "cta": "c"})
    db_session.add(script)
    db_session.commit()
    db_session.refresh(script)

    video = Video(script_id=script.id, status=VideoStatus.pending)
    db_session.add(video)
    db_session.commit()
    db_session.refresh(video)

    pending = client.get("/api/videos", params={"status": "pending"}).json()
    assert any(v["id"] == video.id for v in pending)

    with patch("app.modules.publisher.run.publish_video"):
        resp = client.post(f"/api/videos/{video.id}/approve")
    assert resp.status_code == 200
    assert resp.json()["status"] == "approved"

    app.dependency_overrides.clear()


def test_reject_video_sets_status_and_note(db_session):
    from app.db import get_db

    def _override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db

    script = Script(topic="Test topic 2", script={"hook": "h", "promise": "p", "body": "b", "payoff": "pa", "cta": "c"})
    db_session.add(script)
    db_session.commit()
    db_session.refresh(script)

    video = Video(script_id=script.id, status=VideoStatus.pending)
    db_session.add(video)
    db_session.commit()
    db_session.refresh(video)

    resp = client.post(f"/api/videos/{video.id}/reject", json={"note": "bad hook"})
    assert resp.status_code == 200
    assert resp.json()["status"] == "rejected"
    assert resp.json()["review_note"] == "bad hook"

    app.dependency_overrides.clear()
