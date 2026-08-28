"""Dashboard auth: DASHBOARD_PASSWORD (empty by default) gates every
/api/* request behind a session cookie set by POST /api/auth/login.
Covers both states - auth off (today's default, unchanged behavior) and
auth on - plus the deliberate carve-outs: /health and the auth
endpoints themselves stay reachable either way, and /media is never
gated (it's fetched server-side by Meta with no cookie when publishing
an Instagram Reel - see instagram.py's _video_url()).
"""
from fastapi.testclient import TestClient

from faceless_pipeline.config import settings
from faceless_pipeline.main import app


def test_auth_disabled_by_default_every_endpoint_is_open(monkeypatch):
    monkeypatch.setattr(settings, "dashboard_password", "")
    client = TestClient(app)

    resp = client.get("/api/settings")

    assert resp.status_code == 200


def test_auth_status_reports_disabled_and_authenticated_when_off(monkeypatch):
    monkeypatch.setattr(settings, "dashboard_password", "")
    client = TestClient(app)

    resp = client.get("/api/auth/status")

    assert resp.json() == {"enabled": False, "authenticated": True}


def test_protected_endpoint_requires_login_when_enabled(monkeypatch):
    monkeypatch.setattr(settings, "dashboard_password", "hunter2")
    client = TestClient(app)

    resp = client.get("/api/settings")

    assert resp.status_code == 401


def test_auth_status_and_login_remain_reachable_without_a_session(monkeypatch):
    monkeypatch.setattr(settings, "dashboard_password", "hunter2")
    client = TestClient(app)

    status = client.get("/api/auth/status")
    assert status.status_code == 200
    assert status.json() == {"enabled": True, "authenticated": False}

    login = client.post("/api/auth/login", json={"password": "wrong"})
    assert login.status_code == 401  # reachable, just rejected


def test_correct_password_logs_in_and_unlocks_the_api(monkeypatch):
    monkeypatch.setattr(settings, "dashboard_password", "hunter2")
    client = TestClient(app)

    login = client.post("/api/auth/login", json={"password": "hunter2"})
    assert login.status_code == 200
    assert login.json() == {"authenticated": True}

    resp = client.get("/api/settings")
    assert resp.status_code == 200

    status = client.get("/api/auth/status")
    assert status.json() == {"enabled": True, "authenticated": True}


def test_logout_clears_the_session(monkeypatch):
    monkeypatch.setattr(settings, "dashboard_password", "hunter2")
    client = TestClient(app)
    client.post("/api/auth/login", json={"password": "hunter2"})
    assert client.get("/api/settings").status_code == 200

    logout = client.post("/api/auth/logout")
    assert logout.status_code == 200

    resp = client.get("/api/settings")
    assert resp.status_code == 401


def test_health_is_always_reachable_regardless_of_auth(monkeypatch):
    monkeypatch.setattr(settings, "dashboard_password", "hunter2")
    client = TestClient(app)

    resp = client.get("/health")

    assert resp.status_code == 200


def test_media_is_never_gated_even_with_auth_enabled(monkeypatch, tmp_path):
    """Regression guard: /media has to stay reachable with no session,
    since Meta's servers fetch it directly (no cookie) when publishing
    an Instagram Reel - gating it would silently break that flow."""
    monkeypatch.setattr(settings, "dashboard_password", "hunter2")
    monkeypatch.setattr(settings, "output_dir", str(tmp_path))
    (tmp_path / "video.mp4").write_bytes(b"fake mp4 bytes")
    client = TestClient(app)

    resp = client.get("/media", params={"path": str(tmp_path / "video.mp4")})

    assert resp.status_code == 200


def test_wrong_password_never_creates_a_session(monkeypatch):
    monkeypatch.setattr(settings, "dashboard_password", "hunter2")
    client = TestClient(app)

    client.post("/api/auth/login", json={"password": "wrong"})

    resp = client.get("/api/settings")
    assert resp.status_code == 401
