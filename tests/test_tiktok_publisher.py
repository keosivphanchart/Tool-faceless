"""TikTok Content Posting API v2: the init -> upload -> poll-status flow.

TikTok's real API (open.tiktokapis.com) isn't reachable from this sandbox,
and the interactive OAuth consent step (authorize()) needs a human in a
browser regardless of environment - same situation as YouTube's OAuth flow
already in this codebase. What *is* verifiable here is the HTTP contract
upload_video() drives once a token already exists: real local HTTP server
standing in for TikTok's endpoints, real request bodies, real response
parsing - the same trick used for the LLM provider tests.
"""
import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from faceless_pipeline.config import settings
from faceless_pipeline.modules.publisher import tiktok


class _TikTokHandler(BaseHTTPRequestHandler):
    received: list[dict] = []
    status_sequence: list[str] = ["PUBLISH_COMPLETE"]
    fail_reason = "video_format_check_failed"

    def _read_json(self):
        length = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(length)
        return json.loads(raw) if raw else {}

    def _respond(self, payload, status=200):
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(payload).encode())

    def do_POST(self):
        if self.path == "/v2/post/publish/video/init/":
            body = self._read_json()
            type(self).received.append({"path": self.path, "body": body, "authorization": self.headers.get("Authorization")})
            self._respond(
                {
                    "data": {
                        "publish_id": "publish_abc123",
                        "upload_url": f"http://127.0.0.1:{self.server.server_port}/upload",
                    },
                    "error": {"code": "ok"},
                }
            )
        elif self.path == "/v2/post/publish/status/fetch/":
            body = self._read_json()
            type(self).received.append({"path": self.path, "body": body})
            status = type(self).status_sequence.pop(0) if len(type(self).status_sequence) > 1 else type(self).status_sequence[0]
            data = {"status": status}
            if status == "FAILED":
                data["fail_reason"] = type(self).fail_reason
            self._respond({"data": data, "error": {"code": "ok"}})
        elif self.path == "/v2/oauth/token/":
            length = int(self.headers.get("Content-Length", 0))
            type(self).received.append({"path": self.path, "form": self.rfile.read(length).decode()})
            self._respond({"access_token": "refreshed-token", "refresh_token": "refresh-2", "expires_in": 3600})
        else:
            self._respond({"error": "not found"}, status=404)

    def do_PUT(self):
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length)
        type(self).received.append(
            {"path": self.path, "content_range": self.headers.get("Content-Range"), "bytes": len(body)}
        )
        self._respond({}, status=201)

    def log_message(self, format, *args):
        pass


@pytest.fixture
def tiktok_server(tmp_path):
    _TikTokHandler.received = []
    _TikTokHandler.status_sequence = ["PUBLISH_COMPLETE"]

    server = HTTPServer(("127.0.0.1", 0), _TikTokHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    original = {
        "tiktok_api_base_url": settings.tiktok_api_base_url,
        "tiktok_client_key": settings.tiktok_client_key,
        "tiktok_client_secret": settings.tiktok_client_secret,
        "tiktok_token_file": settings.tiktok_token_file,
    }
    settings.tiktok_api_base_url = f"http://127.0.0.1:{server.server_port}"
    settings.tiktok_client_key = "test-client-key"
    settings.tiktok_client_secret = "test-client-secret"
    settings.tiktok_token_file = str(tmp_path / "tiktok_token.json")

    try:
        yield _TikTokHandler
    finally:
        server.shutdown()
        thread.join()
        for key, value in original.items():
            setattr(settings, key, value)


def _seed_valid_token():
    import time

    tiktok._save_token({"access_token": "cached-token", "refresh_token": "refresh-1", "expires_in": 3600})
    # _save_token stamps obtained_at itself (time.time()), so the token
    # written above is already fresh -- nothing else to backdate.


def _make_video_file(path):
    path.write_bytes(b"fake mp4 bytes for upload test")
    return str(path)


def test_upload_video_happy_path_drives_init_upload_and_poll(tiktok_server, tmp_path):
    _seed_valid_token()
    video_path = _make_video_file(tmp_path / "video.mp4")

    publish_id = tiktok.upload_video(video_path, title="Capybara facts", tags=["capybara", "facts"])

    assert publish_id == "publish_abc123"
    paths = [r["path"] for r in tiktok_server.received]
    assert paths == ["/v2/post/publish/video/init/", "/upload", "/v2/post/publish/status/fetch/"]

    init_req = tiktok_server.received[0]
    assert init_req["authorization"] == "Bearer cached-token"
    assert init_req["body"]["post_info"]["title"] == "Capybara facts #capybara #facts"
    assert init_req["body"]["post_info"]["privacy_level"] == settings.tiktok_default_privacy_level
    assert init_req["body"]["source_info"]["total_chunk_count"] == 1

    upload_req = tiktok_server.received[1]
    assert upload_req["bytes"] == len(b"fake mp4 bytes for upload test")
    assert upload_req["content_range"] == f"bytes 0-{upload_req['bytes'] - 1}/{upload_req['bytes']}"

    status_req = tiktok_server.received[2]
    assert status_req["body"]["publish_id"] == "publish_abc123"


def test_upload_video_polls_through_processing_states(tiktok_server, tmp_path):
    _seed_valid_token()
    tiktok_server.status_sequence = ["PROCESSING_UPLOAD", "PROCESSING_DOWNLOAD", "PUBLISH_COMPLETE"]
    video_path = _make_video_file(tmp_path / "video.mp4")

    publish_id = tiktok.upload_video(video_path, title="t", poll_interval_seconds=0.01)

    assert publish_id == "publish_abc123"
    status_polls = [r for r in tiktok_server.received if r["path"] == "/v2/post/publish/status/fetch/"]
    assert len(status_polls) == 3


def test_upload_video_raises_on_failed_status(tiktok_server, tmp_path):
    _seed_valid_token()
    tiktok_server.status_sequence = ["FAILED"]
    video_path = _make_video_file(tmp_path / "video.mp4")

    with pytest.raises(tiktok.TikTokPublishFailed, match="video_format_check_failed"):
        tiktok.upload_video(video_path, title="t")


def test_upload_video_refreshes_expired_token(tiktok_server, tmp_path):
    import time

    tiktok._save_token({"access_token": "stale-token", "refresh_token": "refresh-1", "expires_in": 3600})
    token = tiktok._load_token()
    token["obtained_at"] = time.time() - 10000  # well past expiry
    tiktok._token_path().write_text(json.dumps(token), encoding="utf-8")

    video_path = _make_video_file(tmp_path / "video.mp4")
    tiktok.upload_video(video_path, title="t")

    refresh_calls = [r for r in tiktok_server.received if r["path"] == "/v2/oauth/token/"]
    assert len(refresh_calls) == 1
    assert "refresh_token=refresh-1" in refresh_calls[0]["form"]

    init_req = [r for r in tiktok_server.received if r["path"] == "/v2/post/publish/video/init/"][0]
    assert init_req["authorization"] == "Bearer refreshed-token"


def test_upload_video_without_cached_token_raises_actionable_error(tiktok_server, tmp_path):
    video_path = _make_video_file(tmp_path / "video.mp4")

    with pytest.raises(RuntimeError, match="authorize"):
        tiktok.upload_video(video_path, title="t")


def test_upload_video_without_client_credentials_raises_not_configured(tiktok_server, tmp_path):
    settings.tiktok_client_key = ""
    video_path = _make_video_file(tmp_path / "video.mp4")

    with pytest.raises(tiktok.TikTokNotConfigured):
        tiktok.upload_video(video_path, title="t")


def test_is_connected_reflects_token_file(tiktok_server):
    assert tiktok.is_connected() is False
    _seed_valid_token()
    assert tiktok.is_connected() is True


def test_disconnect_removes_token_file(tiktok_server):
    _seed_valid_token()
    tiktok.disconnect()
    assert tiktok.is_connected() is False
    tiktok.disconnect()  # missing_ok - disconnecting again is a no-op, not an error


def test_build_authorize_url_uses_configured_redirect_uri(tiktok_server, monkeypatch):
    monkeypatch.setattr(settings, "tiktok_redirect_uri", "http://localhost:8000/api/publish/accounts/tiktok/callback")

    url = tiktok.build_authorize_url()

    assert url.startswith(tiktok.AUTHORIZE_URL)
    assert "client_key=test-client-key" in url
    assert "redirect_uri=http://localhost:8000/api/publish/accounts/tiktok/callback" in url


def test_build_authorize_url_without_credentials_raises(tiktok_server):
    settings.tiktok_client_key = ""

    with pytest.raises(tiktok.TikTokNotConfigured):
        tiktok.build_authorize_url()


def test_complete_authorization_exchanges_code_and_caches_token(tiktok_server):
    tiktok.complete_authorization("some-code")

    token = tiktok._load_token()
    assert token["access_token"] == "refreshed-token"  # the fixture's oauth handler always returns this
    exchange_calls = [r for r in tiktok_server.received if r["path"] == "/v2/oauth/token/"]
    assert len(exchange_calls) == 1
    assert "code=some-code" in exchange_calls[0]["form"]
    assert "grant_type=authorization_code" in exchange_calls[0]["form"]
