"""TikTok performance pull via TikTok's Display/Reporting API.

NOT YET USABLE for the same reason as Module 6's tiktok.py: TikTok's
video/analytics reporting scopes require an approved app. Stub kept in
the same shape as youtube_analytics.fetch_video_performance so run.py can
treat both platforms uniformly once this is implemented.
"""
from app.config import settings


class TikTokNotConfigured(RuntimeError):
    pass


def fetch_video_performance(tiktok_video_id: str, days: int = 7) -> dict:
    if not settings.tiktok_client_key:
        raise TikTokNotConfigured("TikTok API not configured yet — see publisher/tiktok.py for setup notes.")
    raise NotImplementedError("Implement once TikTok reporting API access is approved.")
