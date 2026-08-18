"""TikTok Content Posting API v2 integration.

Posting to any account beyond your own requires TikTok's app review, which
reportedly takes weeks — apply early at
https://developers.tiktok.com/products/content-posting-api/. Your own
developer/test account can authorize and post immediately after creating a
sandbox app, before that review completes, which is what this module is
built and tested against.

Flow (https://developers.tiktok.com/doc/content-posting-api-reference-direct-post):
  1. One-time interactive OAuth: authorize() opens a browser for user
     consent, catches the redirect on a local server, exchanges the code
     for an access + refresh token, and caches both at TIKTOK_TOKEN_FILE.
  2. upload_video() then, per call:
       a. POST /v2/post/publish/video/init/ with post_info + source_info
          -> {publish_id, upload_url}
       b. PUT the video bytes to upload_url
       c. Poll /v2/post/publish/status/fetch/ with publish_id until the
          post leaves the PROCESSING_* states

TIKTOK_API_BASE_URL defaults to TikTok's real endpoint but is overridable
so the init/upload/poll HTTP contract can be exercised against a real
local server in tests, without needing a live TikTok app.
"""
import json
import logging
import time
from pathlib import Path

from faceless_pipeline.config import settings

logger = logging.getLogger(__name__)

AUTHORIZE_URL = "https://www.tiktok.com/v2/auth/authorize/"
SCOPES = "video.publish"

# PUBLISH_COMPLETE / FAILED / SEND_TO_USER_INBOX are terminal; the
# PROCESSING_* states mean "keep polling".
TERMINAL_STATUSES = {"PUBLISH_COMPLETE", "FAILED", "SEND_TO_USER_INBOX"}


class TikTokNotConfigured(RuntimeError):
    pass


class TikTokPublishFailed(RuntimeError):
    pass


def _token_path() -> Path:
    return Path(settings.tiktok_token_file)


def _require_client_credentials():
    if not settings.tiktok_client_key or not settings.tiktok_client_secret:
        raise TikTokNotConfigured(
            "TikTok Content Posting API isn't configured yet — set TIKTOK_CLIENT_KEY / "
            "TIKTOK_CLIENT_SECRET (see this module's docstring for setup)."
        )


def _save_token(token: dict) -> None:
    token = dict(token)
    token["obtained_at"] = time.time()
    _token_path().parent.mkdir(parents=True, exist_ok=True)
    _token_path().write_text(json.dumps(token), encoding="utf-8")


def _load_token() -> dict | None:
    if not _token_path().exists():
        return None
    return json.loads(_token_path().read_text(encoding="utf-8"))


def _exchange_code_for_token(code: str) -> dict:
    import requests

    response = requests.post(
        f"{settings.tiktok_api_base_url}/v2/oauth/token/",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        data={
            "client_key": settings.tiktok_client_key,
            "client_secret": settings.tiktok_client_secret,
            "code": code,
            "grant_type": "authorization_code",
            "redirect_uri": settings.tiktok_redirect_uri,
        },
        timeout=30,
    )
    response.raise_for_status()
    return response.json()


def _refresh_access_token(refresh_token: str) -> dict:
    import requests

    response = requests.post(
        f"{settings.tiktok_api_base_url}/v2/oauth/token/",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        data={
            "client_key": settings.tiktok_client_key,
            "client_secret": settings.tiktok_client_secret,
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
        },
        timeout=30,
    )
    response.raise_for_status()
    return response.json()


def _get_access_token() -> str:
    _require_client_credentials()
    token = _load_token()
    if token is None:
        raise RuntimeError(
            f"No cached TikTok token at {settings.tiktok_token_file} — run "
            "`python -m faceless_pipeline.modules.publisher.tiktok` once to authorize interactively."
        )

    # expires_in is seconds from obtained_at; refresh a bit early (60s
    # margin) rather than racing a token that expires mid-upload.
    obtained_at = token.get("obtained_at", 0)
    expires_in = token.get("expires_in", 0)
    if time.time() < obtained_at + expires_in - 60:
        return token["access_token"]

    refreshed = _refresh_access_token(token["refresh_token"])
    _save_token(refreshed)
    return refreshed["access_token"]


def authorize() -> None:
    """One-time interactive setup: opens a browser for TikTok's OAuth
    consent screen, runs a short-lived local HTTP server to catch the
    redirect (matching TIKTOK_REDIRECT_URI), exchanges the returned code
    for a token pair, and caches it at TIKTOK_TOKEN_FILE for upload_video()
    to use on every subsequent call. Interactive by nature (a human must
    approve in the browser), so this is meant to be run once by hand, not
    something an automated pipeline run invokes itself.
    """
    import webbrowser
    from http.server import BaseHTTPRequestHandler, HTTPServer
    from urllib.parse import parse_qs, urlparse

    _require_client_credentials()
    redirect = urlparse(settings.tiktok_redirect_uri)
    result: dict = {}

    class _CallbackHandler(BaseHTTPRequestHandler):
        def do_GET(self):
            query = parse_qs(urlparse(self.path).query)
            if "code" in query:
                result["code"] = query["code"][0]
                body = b"TikTok authorized. You can close this tab."
            else:
                result["error"] = query.get("error", ["unknown_error"])[0]
                body = b"TikTok authorization failed. Check the terminal and try again."
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, format, *args):
            pass

    server = HTTPServer((redirect.hostname, redirect.port), _CallbackHandler)

    auth_url = (
        f"{AUTHORIZE_URL}?client_key={settings.tiktok_client_key}&scope={SCOPES}"
        f"&response_type=code&redirect_uri={settings.tiktok_redirect_uri}&state=faceless_pipeline"
    )
    logger.info("Opening browser for TikTok authorization: %s", auth_url)
    webbrowser.open(auth_url)
    server.handle_request()  # blocks for exactly one request, then returns
    server.server_close()

    if "error" in result:
        raise RuntimeError(f"TikTok authorization failed: {result['error']}")

    token = _exchange_code_for_token(result["code"])
    _save_token(token)
    logger.info("TikTok token cached at %s", settings.tiktok_token_file)


def upload_video(
    file_path: str,
    title: str,
    tags: list[str] | None = None,
    privacy_level: str | None = None,
    poll_interval_seconds: float = 3.0,
    max_poll_attempts: int = 40,
) -> str:
    """Posts `file_path` via the Content Posting API's direct-post flow
    and returns the resulting publish_id. Raises TikTokPublishFailed if
    TikTok reports the post as FAILED after upload.
    """
    import requests

    access_token = _get_access_token()
    file_size = Path(file_path).stat().st_size
    caption = title if not tags else f"{title} " + " ".join(f"#{t.lstrip('#')}" for t in tags)

    init_response = requests.post(
        f"{settings.tiktok_api_base_url}/v2/post/publish/video/init/",
        headers={"Authorization": f"Bearer {access_token}", "Content-Type": "application/json; charset=UTF-8"},
        json={
            "post_info": {
                "title": caption[:2200],
                "privacy_level": privacy_level or settings.tiktok_default_privacy_level,
                "disable_duet": False,
                "disable_comment": False,
                "disable_stitch": False,
            },
            "source_info": {
                "source": "FILE_UPLOAD",
                "video_size": file_size,
                "chunk_size": file_size,
                "total_chunk_count": 1,
            },
        },
        timeout=30,
    )
    init_response.raise_for_status()
    init_data = init_response.json()
    error = init_data.get("error", {})
    if error and error.get("code") not in (None, "ok"):
        raise TikTokPublishFailed(f"TikTok publish init failed: {error}")

    publish_id = init_data["data"]["publish_id"]
    upload_url = init_data["data"]["upload_url"]

    with open(file_path, "rb") as f:
        upload_response = requests.put(
            upload_url,
            headers={"Content-Type": "video/mp4", "Content-Range": f"bytes 0-{file_size - 1}/{file_size}"},
            data=f,
            timeout=300,
        )
    upload_response.raise_for_status()

    for _ in range(max_poll_attempts):
        status_response = requests.post(
            f"{settings.tiktok_api_base_url}/v2/post/publish/status/fetch/",
            headers={"Authorization": f"Bearer {access_token}", "Content-Type": "application/json; charset=UTF-8"},
            json={"publish_id": publish_id},
            timeout=30,
        )
        status_response.raise_for_status()
        status_data = status_response.json()["data"]
        status = status_data.get("status")

        if status == "FAILED":
            raise TikTokPublishFailed(f"TikTok publish {publish_id} failed: {status_data.get('fail_reason')}")
        if status in TERMINAL_STATUSES:
            return publish_id

        time.sleep(poll_interval_seconds)

    logger.warning(
        "TikTok publish %s still processing after %d polls — treating as accepted, check the "
        "TikTok app for final status", publish_id, max_poll_attempts,
    )
    return publish_id


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    authorize()
