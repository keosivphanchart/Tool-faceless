"""Pulls per-video performance from the YouTube Analytics API (reports.query).

Requires a separate OAuth token with the yt-analytics.readonly scope —
see YOUTUBE_ANALYTICS_TOKEN_FILE. Reuses the same client secrets file as
the publisher (Module 6) OAuth app.
"""
import logging
from datetime import date, timedelta
from pathlib import Path

from faceless_pipeline.config import settings

logger = logging.getLogger(__name__)

SCOPES = ["https://www.googleapis.com/auth/yt-analytics.readonly"]


def _get_analytics_service():
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from googleapiclient.discovery import build

    creds = None
    token_path = Path(settings.youtube_analytics_token_file)
    if token_path.exists():
        creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(settings.youtube_client_secrets_file, SCOPES)
            creds = flow.run_local_server(port=0)
        token_path.parent.mkdir(parents=True, exist_ok=True)
        token_path.write_text(creds.to_json(), encoding="utf-8")

    return build("youtubeAnalytics", "v2", credentials=creds)


def fetch_video_performance(youtube_video_id: str, days: int = 7) -> dict:
    """Returns {"views": int, "retention_pct": float, "completion_pct": float,
    "likes": int, "shares": int} for the trailing `days` window."""
    service = _get_analytics_service()
    end = date.today()
    start = end - timedelta(days=days)

    response = (
        service.reports()
        .query(
            ids="channel==MINE",
            startDate=start.isoformat(),
            endDate=end.isoformat(),
            metrics="views,averageViewPercentage,likes,shares",
            filters=f"video=={youtube_video_id}",
        )
        .execute()
    )

    rows = response.get("rows") or [[0, 0.0, 0, 0]]
    views, avg_view_pct, likes, shares = rows[0]
    return {
        "views": int(views),
        "retention_pct": float(avg_view_pct),
        "completion_pct": float(avg_view_pct),  # YouTube reports one retention curve; reuse it
        "likes": int(likes),
        "shares": int(shares),
    }
