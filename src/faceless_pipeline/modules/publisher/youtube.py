"""YouTube Data API videos.insert integration, including OAuth setup and
quota handling.

One-time setup:
  1. Create an OAuth client (Desktop app) in Google Cloud Console, enable
     the YouTube Data API v3, download the client secret JSON to the path
     in YOUTUBE_CLIENT_SECRETS_FILE.
  2. First run will open a browser for the OAuth consent flow and cache
     the resulting token at YOUTUBE_TOKEN_FILE for reuse.

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


def _get_authenticated_service():
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from googleapiclient.discovery import build

    creds = None
    token_path = Path(settings.youtube_token_file)
    if token_path.exists():
        creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not Path(settings.youtube_client_secrets_file).exists():
                raise RuntimeError(
                    f"YouTube OAuth client secrets not found at "
                    f"{settings.youtube_client_secrets_file}. See youtube.py docstring for setup."
                )
            flow = InstalledAppFlow.from_client_secrets_file(settings.youtube_client_secrets_file, SCOPES)
            creds = flow.run_local_server(port=0)

        token_path.parent.mkdir(parents=True, exist_ok=True)
        token_path.write_text(creds.to_json(), encoding="utf-8")

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
