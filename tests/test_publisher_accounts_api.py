"""Dashboard-driven connect/disconnect endpoints for YouTube/TikTok/
Instagram accounts: /status reports configured+connected, /connect
redirects the browser to the platform's consent screen, /callback
exchanges the code and redirects back to the dashboard, /disconnect
clears the cached token. The actual OAuth exchange is exercised in
test_youtube_publisher, test_tiktok_publisher, and
test_instagram_publisher; here we only check the HTTP wiring, mocking
the module-level connect/exchange calls.
"""
from fastapi.testclient import TestClient

from faceless_pipeline.config import settings
from faceless_pipeline.main import app
from faceless_pipeline.modules.publisher import instagram, tiktok, youtube

client = TestClient(app, follow_redirects=False)


def test_accounts_status_reports_configured_and_connected(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "youtube_client_secrets_file", str(tmp_path / "missing.json"))
    monkeypatch.setattr(settings, "youtube_token_file", str(tmp_path / "yt_token.json"))
    monkeypatch.setattr(settings, "tiktok_client_key", "")
    monkeypatch.setattr(settings, "tiktok_client_secret", "")
    monkeypatch.setattr(settings, "tiktok_token_file", str(tmp_path / "tt_token.json"))
    monkeypatch.setattr(settings, "instagram_app_id", "")
    monkeypatch.setattr(settings, "instagram_app_secret", "")
    monkeypatch.setattr(settings, "instagram_token_file", str(tmp_path / "ig_token.json"))

    resp = client.get("/api/publish/accounts/status")

    assert resp.status_code == 200
    assert resp.json() == {
        "youtube": {"configured": False, "connected": False},
        "tiktok": {"configured": False, "connected": False},
        "instagram": {"configured": False, "connected": False},
    }


def test_youtube_connect_redirects_to_authorize_url(monkeypatch):
    monkeypatch.setattr(youtube, "build_authorize_url", lambda: "https://accounts.google.com/authorize?x=1")

    resp = client.get("/api/publish/accounts/youtube/connect")

    assert resp.status_code in (302, 307)
    assert resp.headers["location"] == "https://accounts.google.com/authorize?x=1"


def test_youtube_connect_without_client_secrets_returns_400(monkeypatch):
    def _raise():
        raise RuntimeError("no secrets")

    monkeypatch.setattr(youtube, "build_authorize_url", _raise)

    resp = client.get("/api/publish/accounts/youtube/connect")

    assert resp.status_code == 400


def test_youtube_callback_success_saves_token_and_redirects(monkeypatch):
    monkeypatch.setattr(settings, "dashboard_url", "http://localhost:5173")
    calls = {}
    monkeypatch.setattr(youtube, "complete_authorization", lambda code: calls.setdefault("code", code))

    resp = client.get("/api/publish/accounts/youtube/callback", params={"code": "abc123"})

    assert resp.headers["location"] == "http://localhost:5173/settings?connected=youtube"
    assert calls["code"] == "abc123"


def test_youtube_callback_error_param_redirects_with_error(monkeypatch):
    monkeypatch.setattr(settings, "dashboard_url", "http://localhost:5173")

    resp = client.get("/api/publish/accounts/youtube/callback", params={"error": "access_denied"})

    assert resp.headers["location"] == "http://localhost:5173/settings?error=youtube_access_denied"


def test_youtube_callback_exchange_failure_redirects_with_error(monkeypatch):
    monkeypatch.setattr(settings, "dashboard_url", "http://localhost:5173")

    def _raise(code):
        raise RuntimeError("boom")

    monkeypatch.setattr(youtube, "complete_authorization", _raise)

    resp = client.get("/api/publish/accounts/youtube/callback", params={"code": "abc"})

    assert resp.headers["location"] == "http://localhost:5173/settings?error=youtube_authorization_failed"


def test_youtube_disconnect_removes_token(tmp_path, monkeypatch):
    token_path = tmp_path / "yt_token.json"
    token_path.write_text("{}")
    monkeypatch.setattr(settings, "youtube_token_file", str(token_path))

    resp = client.post("/api/publish/accounts/youtube/disconnect")

    assert resp.status_code == 200
    assert resp.json() == {"connected": False}
    assert not token_path.exists()


def test_tiktok_connect_redirects_to_authorize_url(monkeypatch):
    monkeypatch.setattr(tiktok, "build_authorize_url", lambda: "https://www.tiktok.com/v2/auth/authorize/?x=1")

    resp = client.get("/api/publish/accounts/tiktok/connect")

    assert resp.headers["location"] == "https://www.tiktok.com/v2/auth/authorize/?x=1"


def test_tiktok_connect_without_credentials_returns_400(monkeypatch):
    monkeypatch.setattr(settings, "tiktok_client_key", "")
    monkeypatch.setattr(settings, "tiktok_client_secret", "")

    resp = client.get("/api/publish/accounts/tiktok/connect")

    assert resp.status_code == 400


def test_tiktok_callback_success_saves_token_and_redirects(monkeypatch):
    monkeypatch.setattr(settings, "dashboard_url", "http://localhost:5173")
    calls = {}
    monkeypatch.setattr(tiktok, "complete_authorization", lambda code: calls.setdefault("code", code))

    resp = client.get("/api/publish/accounts/tiktok/callback", params={"code": "xyz"})

    assert resp.headers["location"] == "http://localhost:5173/settings?connected=tiktok"
    assert calls["code"] == "xyz"


def test_tiktok_callback_exchange_failure_redirects_with_error(monkeypatch):
    monkeypatch.setattr(settings, "dashboard_url", "http://localhost:5173")

    def _raise(code):
        raise RuntimeError("boom")

    monkeypatch.setattr(tiktok, "complete_authorization", _raise)

    resp = client.get("/api/publish/accounts/tiktok/callback", params={"code": "xyz"})

    assert resp.headers["location"] == "http://localhost:5173/settings?error=tiktok_authorization_failed"


def test_tiktok_disconnect_removes_token(tmp_path, monkeypatch):
    token_path = tmp_path / "tt_token.json"
    token_path.write_text("{}")
    monkeypatch.setattr(settings, "tiktok_token_file", str(token_path))

    resp = client.post("/api/publish/accounts/tiktok/disconnect")

    assert resp.status_code == 200
    assert not token_path.exists()


def test_instagram_connect_redirects_to_authorize_url(monkeypatch):
    monkeypatch.setattr(instagram, "build_authorize_url", lambda: "https://www.facebook.com/v19.0/dialog/oauth?x=1")

    resp = client.get("/api/publish/accounts/instagram/connect")

    assert resp.headers["location"] == "https://www.facebook.com/v19.0/dialog/oauth?x=1"


def test_instagram_connect_without_credentials_returns_400(monkeypatch):
    monkeypatch.setattr(settings, "instagram_app_id", "")
    monkeypatch.setattr(settings, "instagram_app_secret", "")

    resp = client.get("/api/publish/accounts/instagram/connect")

    assert resp.status_code == 400


def test_instagram_callback_success_saves_token_and_redirects(monkeypatch):
    monkeypatch.setattr(settings, "dashboard_url", "http://localhost:5173")
    calls = {}
    monkeypatch.setattr(instagram, "complete_authorization", lambda code: calls.setdefault("code", code))

    resp = client.get("/api/publish/accounts/instagram/callback", params={"code": "abc123"})

    assert resp.headers["location"] == "http://localhost:5173/settings?connected=instagram"
    assert calls["code"] == "abc123"


def test_instagram_callback_exchange_failure_redirects_with_error(monkeypatch):
    monkeypatch.setattr(settings, "dashboard_url", "http://localhost:5173")

    def _raise(code):
        raise RuntimeError("boom")

    monkeypatch.setattr(instagram, "complete_authorization", _raise)

    resp = client.get("/api/publish/accounts/instagram/callback", params={"code": "xyz"})

    assert resp.headers["location"] == "http://localhost:5173/settings?error=instagram_authorization_failed"


def test_instagram_disconnect_removes_token(tmp_path, monkeypatch):
    token_path = tmp_path / "ig_token.json"
    token_path.write_text("{}")
    monkeypatch.setattr(settings, "instagram_token_file", str(token_path))

    resp = client.post("/api/publish/accounts/instagram/disconnect")

    assert resp.status_code == 200
    assert not token_path.exists()
