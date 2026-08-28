"""YouTube Data API videos.insert integration, including OAuth setup and
quota handling.

One-time setup:
  1. Create an OAuth client (Web application) in Google Cloud Console,
     enable the YouTube Data API v3, add YOUTUBE_REDIRECT_URI as an
     authorized redirect URI, and download the client secret JSON to the
     path in YOUTUBE_CLIENT_SECRETS_FILE.
  2. Connect the account from the dashboard's Settings page ("Connect
     YouTube") — this drives the browser through Google's consent screen
     and caches the resulting token at YOUTUBE_TOKEN_FILE for reuse.

Quota: videos.insert costs 1600 units against YouTube's default 10,000
units/day quota — roughly 6 uploads/day per project before you need to
request a quota increase.
"""
import logging
from pathlib import Path

from faceless_pipeline.config import settings

logger = logging.getLogger(__name__)

SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]

QUOTA_EXCEEDED_REASONS = {"quotaExceeded", "dailyLimitExceeded"}


class YouTubeQuotaExceeded(RuntimeError):
    pass


def _client_secrets_path() -> Path:
    return Path(settings.youtube_client_secrets_file)


def _token_path() -> Path:
    return Path(settings.youtube_token_file)


def _web_flow():
    from google_auth_oauthlib.flow import Flow

    if not _client_secrets_path().exists():
        raise RuntimeError(
            f"YouTube OAuth client secrets not found at "
            f"{settings.youtube_client_secrets_file}. See youtube.py docstring for setup."
        )
    return Flow.from_client_secrets_file(
        str(_client_secrets_path()), scopes=SCOPES, redirect_uri=settings.youtube_redirect_uri
    )


def is_connected() -> bool:
    return _token_path().is_file()


def disconnect() -> None:
    _token_path().unlink(missing_ok=True)


def build_authorize_url() -> str:
    """Starts the dashboard-driven connect flow: the URL to send the
    browser to for Google's consent screen."""
    flow = _web_flow()
    auth_url, _ = flow.authorization_url(access_type="offline", include_granted_scopes="true", prompt="consent")
    return auth_url


def complete_authorization(code: str) -> None:
    """Finishes the connect flow: exchanges the code Google's redirect
    handed back for a token and caches it at YOUTUBE_TOKEN_FILE."""
    flow = _web_flow()
    flow.fetch_token(code=code)
    token_path = _token_path()
    token_path.parent.mkdir(parents=True, exist_ok=True)
    token_path.write_text(flow.credentials.to_json(), encoding="utf-8")


def _get_authenticated_service():
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build

    token_path = _token_path()
    if not token_path.exists():
        raise RuntimeError(
            "No cached YouTube token — connect a YouTube account from the dashboard's "
            "Settings page before publishing."
        )

    creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)
    if not creds.valid:
        if creds.expired and creds.refresh_token:
            creds.refresh(Request())
            token_path.write_text(creds.to_json(), encoding="utf-8")
        else:
            raise RuntimeError(
                "Cached YouTube token is invalid and can't be refreshed — reconnect the "
                "account from the dashboard's Settings page."
            )

    return build("youtube", "v3", credentials=creds)


def upload_video(
    file_path: str,
    title: str,
    description: str,
    tags: list[str] | None = None,
    privacy_status: str = "private",
    category_id: str = "22",
) -> str:
    """Uploads `file_path` and returns the resulting YouTube video ID."""
    from googleapiclient.errors import HttpError
    from googleapiclient.http import MediaFileUpload

    youtube = _get_authenticated_service()

    body = {
        "snippet": {
            "title": title[:100],
            "description": description[:5000],
            "tags": tags or [],
            "categoryId": category_id,
        },
        "status": {"privacyStatus": privacy_status, "selfDeclaredMadeForKids": False},
    }
    media = MediaFileUpload(file_path, chunksize=-1, resumable=True)

    try:
        request = youtube.videos().insert(part="snippet,status", body=body, media_body=media)
        response = None
        while response is None:
            status, response = request.next_chunk()
            if status:
                logger.info("Upload progress: %d%%", int(status.progress() * 100))
        return response["id"]
    except HttpError as exc:
        reason = ""
        try:
            reason = exc.error_details[0].get("reason", "")
        except Exception:
            pass
        if reason in QUOTA_EXCEEDED_REASONS or exc.status_code == 403:
            raise YouTubeQuotaExceeded(f"YouTube upload quota exceeded: {exc}") from exc
        raise
