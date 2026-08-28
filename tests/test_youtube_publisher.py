"""YouTube publish-account connect flow: is_connected/disconnect track
the cached token file, build_authorize_url builds a real Google consent
URL from the (web-type) client secrets file without touching the
network, and complete_authorization exchanges a code for a token and
caches it — exercised here against a fake Flow since the real exchange
is an HTTP call to Google.
"""
import json

import pytest

from faceless_pipeline.config import settings
from faceless_pipeline.modules.publisher import youtube


def test_is_connected_reflects_token_file(tmp_path, monkeypatch):
    token_path = tmp_path / "yt_token.json"
    monkeypatch.setattr(settings, "youtube_token_file", str(token_path))

    assert youtube.is_connected() is False
    token_path.write_text("{}")
    assert youtube.is_connected() is True


def test_disconnect_removes_token_file(tmp_path, monkeypatch):
    token_path = tmp_path / "yt_token.json"
    token_path.write_text("{}")
    monkeypatch.setattr(settings, "youtube_token_file", str(token_path))

    youtube.disconnect()

    assert not token_path.exists()
    youtube.disconnect()  # missing_ok - disconnecting again is a no-op, not an error


def test_build_authorize_url_uses_web_client_and_configured_redirect_uri(tmp_path, monkeypatch):
    secrets_path = tmp_path / "client_secret.json"
    secrets_path.write_text(
        json.dumps(
            {
                "web": {
                    "client_id": "test-client-id.apps.googleusercontent.com",
                    "client_secret": "test-secret",
                    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                    "token_uri": "https://oauth2.googleapis.com/token",
                }
            }
        )
    )
    monkeypatch.setattr(settings, "youtube_client_secrets_file", str(secrets_path))
    monkeypatch.setattr(
        settings, "youtube_redirect_uri", "http://localhost:8000/api/publish/accounts/youtube/callback"
    )

    auth_url = youtube.build_authorize_url()

    assert auth_url.startswith("https://accounts.google.com/o/oauth2/auth?")
    assert "client_id=test-client-id.apps.googleusercontent.com" in auth_url
    assert "redirect_uri=http%3A%2F%2Flocalhost%3A8000%2Fapi%2Fpublish%2Faccounts%2Fyoutube%2Fcallback" in auth_url


def test_build_authorize_url_without_client_secrets_raises(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "youtube_client_secrets_file", str(tmp_path / "missing.json"))

    with pytest.raises(RuntimeError, match="client secrets not found"):
        youtube.build_authorize_url()


def test_complete_authorization_saves_credentials_json(tmp_path, monkeypatch):
    token_path = tmp_path / "yt_token.json"
    monkeypatch.setattr(settings, "youtube_token_file", str(token_path))

    class _FakeCreds:
        def to_json(self):
            return json.dumps({"token": "fake-access-token"})

    class _FakeFlow:
        credentials = _FakeCreds()

        def fetch_token(self, code):
            assert code == "auth-code-123"

    monkeypatch.setattr(youtube, "_web_flow", lambda: _FakeFlow())

    youtube.complete_authorization("auth-code-123")

    assert json.loads(token_path.read_text()) == {"token": "fake-access-token"}
