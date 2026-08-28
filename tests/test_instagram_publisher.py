"""Instagram Reels via the Meta Graph API: the OAuth code->long-lived
token->Page->IG-business-account chain in complete_authorization(), and
the create->poll->publish flow in upload_video(). Meta's real API isn't
reachable from this sandbox, so - same trick as the TikTok/YouTube
publisher tests - a real local HTTP server stands in for
graph.facebook.com, with real request/response bodies exercising the
actual HTTP contract.
"""
import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlparse

import pytest

from faceless_pipeline.config import settings
from faceless_pipeline.modules.publisher import instagram


class _GraphHandler(BaseHTTPRequestHandler):
    received: list[dict] = []
    media_status_sequence: list[str] = ["FINISHED"]
    accounts_response: dict = {
        "data": [{"id": "page-123", "name": "My Page", "access_token": "page-access-token"}]
    }
    ig_business_account: dict | None = {"id": "ig-user-1"}

    def _respond(self, payload, status=200):
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(payload).encode())

    def _read_form(self):
        length = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(length).decode()
        return {k: v[0] for k, v in parse_qs(raw).items()}

    def do_GET(self):
        parsed = urlparse(self.path)
        query = {k: v[0] for k, v in parse_qs(parsed.query).items()}
        type(self).received.append({"method": "GET", "path": parsed.path, "query": query})

        if parsed.path == "/oauth/access_token":
            if query.get("grant_type") == "fb_exchange_token":
                self._respond({"access_token": "long-lived-user-token", "token_type": "bearer"})
            else:
                self._respond({"access_token": "short-lived-user-token", "token_type": "bearer"})
        elif parsed.path == "/me/accounts":
            self._respond(type(self).accounts_response)
        elif parsed.path == "/page-123":
            if type(self).ig_business_account is None:
                self._respond({})
            else:
                self._respond({"instagram_business_account": type(self).ig_business_account})
        elif parsed.path == "/creation-1":
            status = (
                type(self).media_status_sequence.pop(0)
                if len(type(self).media_status_sequence) > 1
                else type(self).media_status_sequence[0]
            )
            self._respond({"status_code": status})
        else:
            self._respond({"error": {"message": "not found"}}, status=404)

    def do_POST(self):
        parsed = urlparse(self.path)
        body = self._read_form()
        type(self).received.append({"method": "POST", "path": parsed.path, "body": body})

        if parsed.path == "/ig-user-1/media":
            self._respond({"id": "creation-1"})
        elif parsed.path == "/ig-user-1/media_publish":
            self._respond({"id": "published-media-1"})
        else:
            self._respond({"error": {"message": "not found"}}, status=404)

    def log_message(self, format, *args):
        pass


@pytest.fixture
def instagram_server(tmp_path):
    _GraphHandler.received = []
    _GraphHandler.media_status_sequence = ["FINISHED"]
    _GraphHandler.accounts_response = {
        "data": [{"id": "page-123", "name": "My Page", "access_token": "page-access-token"}]
    }
    _GraphHandler.ig_business_account = {"id": "ig-user-1"}

    server = HTTPServer(("127.0.0.1", 0), _GraphHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    original = {
        "instagram_api_base_url": settings.instagram_api_base_url,
        "instagram_app_id": settings.instagram_app_id,
        "instagram_app_secret": settings.instagram_app_secret,
        "instagram_token_file": settings.instagram_token_file,
        "instagram_redirect_uri": settings.instagram_redirect_uri,
        "public_base_url": settings.public_base_url,
    }
    settings.instagram_api_base_url = f"http://127.0.0.1:{server.server_port}"
    settings.instagram_app_id = "test-app-id"
    settings.instagram_app_secret = "test-app-secret"
    settings.instagram_token_file = str(tmp_path / "instagram_token.json")
    settings.instagram_redirect_uri = "http://localhost:8000/api/publish/accounts/instagram/callback"
    settings.public_base_url = "https://example.com"

    try:
        yield _GraphHandler
    finally:
        server.shutdown()
        thread.join()
        for key, value in original.items():
            setattr(settings, key, value)


def _make_video_file(path):
    path.write_bytes(b"fake mp4 bytes for upload test")
    return str(path)


def test_is_connected_reflects_token_file(instagram_server):
    assert instagram.is_connected() is False
    instagram.complete_authorization("auth-code")
    assert instagram.is_connected() is True


def test_disconnect_removes_token_file(instagram_server):
    instagram.complete_authorization("auth-code")
    instagram.disconnect()
    assert instagram.is_connected() is False
    instagram.disconnect()  # missing_ok - disconnecting again is a no-op, not an error


def test_build_authorize_url_uses_configured_app_id_and_redirect_uri(instagram_server):
    url = instagram.build_authorize_url()

    assert url.startswith(instagram.AUTHORIZE_URL)
    assert "client_id=test-app-id" in url
    assert "redirect_uri=http://localhost:8000/api/publish/accounts/instagram/callback" in url


def test_build_authorize_url_without_credentials_raises():
    settings.instagram_app_id = ""
    try:
        with pytest.raises(instagram.InstagramNotConfigured):
            instagram.build_authorize_url()
    finally:
        settings.instagram_app_id = "test-app-id"


def test_complete_authorization_walks_the_oauth_chain_and_caches_token(instagram_server):
    instagram.complete_authorization("auth-code-123")

    saved = json.loads(open(settings.instagram_token_file).read())
    assert saved == {
        "page_access_token": "page-access-token",
        "page_id": "page-123",
        "page_name": "My Page",
        "ig_user_id": "ig-user-1",
    }

    # both leg of the token exchange happened, code was forwarded on the first
    exchange_calls = [r for r in instagram_server.received if r["path"] == "/oauth/access_token"]
    assert len(exchange_calls) == 2
    assert exchange_calls[0]["query"]["code"] == "auth-code-123"
    assert exchange_calls[1]["query"]["fb_exchange_token"] == "short-lived-user-token"


def test_complete_authorization_without_pages_raises(instagram_server):
    instagram_server.accounts_response = {"data": []}

    with pytest.raises(instagram.InstagramPublishFailed, match="no Pages"):
        instagram.complete_authorization("auth-code")


def test_complete_authorization_without_linked_ig_account_raises(instagram_server):
    instagram_server.ig_business_account = None

    with pytest.raises(instagram.InstagramPublishFailed, match="no linked Instagram"):
        instagram.complete_authorization("auth-code")


def test_upload_video_happy_path_drives_create_poll_and_publish(instagram_server, tmp_path):
    instagram.complete_authorization("auth-code")
    video_path = _make_video_file(tmp_path / "video.mp4")

    media_id = instagram.upload_video(video_path, title="Capybara facts", tags=["capybara", "facts"])

    assert media_id == "published-media-1"
    creates = [r for r in instagram_server.received if r["path"] == "/ig-user-1/media"]
    assert len(creates) == 1
    assert creates[0]["body"]["caption"] == "Capybara facts #capybara #facts"
    assert creates[0]["body"]["media_type"] == "REELS"

    publishes = [r for r in instagram_server.received if r["path"] == "/ig-user-1/media_publish"]
    assert len(publishes) == 1
    assert publishes[0]["body"]["creation_id"] == "creation-1"


def test_upload_video_builds_public_video_url_from_public_base_url(instagram_server, tmp_path):
    instagram.complete_authorization("auth-code")
    video_path = _make_video_file(tmp_path / "video.mp4")

    instagram.upload_video(video_path, title="t")

    creates = [r for r in instagram_server.received if r["path"] == "/ig-user-1/media"]
    assert creates[0]["body"]["video_url"].startswith("https://example.com/media?path=")


def test_upload_video_without_public_base_url_raises_not_configured(instagram_server, tmp_path):
    instagram.complete_authorization("auth-code")
    settings.public_base_url = ""
    video_path = _make_video_file(tmp_path / "video.mp4")

    with pytest.raises(instagram.InstagramNotConfigured, match="PUBLIC_BASE_URL"):
        instagram.upload_video(video_path, title="t")


def test_upload_video_polls_through_in_progress_states(instagram_server, tmp_path):
    instagram.complete_authorization("auth-code")
    instagram_server.media_status_sequence = ["IN_PROGRESS", "IN_PROGRESS", "FINISHED"]
    video_path = _make_video_file(tmp_path / "video.mp4")

    media_id = instagram.upload_video(video_path, title="t", poll_interval_seconds=0.01)

    assert media_id == "published-media-1"
    status_polls = [r for r in instagram_server.received if r["path"] == "/creation-1"]
    assert len(status_polls) == 3


def test_upload_video_raises_on_error_status(instagram_server, tmp_path):
    instagram.complete_authorization("auth-code")
    instagram_server.media_status_sequence = ["ERROR"]
    video_path = _make_video_file(tmp_path / "video.mp4")

    with pytest.raises(instagram.InstagramPublishFailed):
        instagram.upload_video(video_path, title="t")


def test_upload_video_without_cached_token_raises_actionable_error(instagram_server, tmp_path):
    video_path = _make_video_file(tmp_path / "video.mp4")

    with pytest.raises(RuntimeError, match="connect an Instagram"):
        instagram.upload_video(video_path, title="t")
