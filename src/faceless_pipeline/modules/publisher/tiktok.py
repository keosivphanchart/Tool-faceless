"""TikTok Content Posting API integration.

NOT YET USABLE: TikTok requires a Content Posting API app review before
any account beyond your own test accounts can post via the API, and that
review reportedly takes weeks. Apply early at
https://developers.tiktok.com/products/content-posting-api/ before you
need this — this stub is ready to fill in once TIKTOK_CLIENT_KEY /
TIKTOK_CLIENT_SECRET are approved and issued.

Expected flow once approved (v2 Content Posting API):
  1. OAuth 2.0 authorization to get a user access token (scope: video.publish)
  2. POST /v2/post/publish/video/init/ with post_info + source_info to get
     an upload URL
  3. PUT the video bytes to that upload URL
  4. Poll /v2/post/publish/status/fetch/ until the post is published
"""
from faceless_pipeline.config import settings


class TikTokNotConfigured(RuntimeError):
    pass


def upload_video(file_path: str, title: str, tags: list[str] | None = None) -> str:
    if not settings.tiktok_client_key or not settings.tiktok_client_secret:
        raise TikTokNotConfigured(
            "TikTok Content Posting API isn't configured/approved yet. "
            "Apply for API access early (it takes weeks) — see this module's docstring."
        )
    raise NotImplementedError("Implement the v2 Content Posting API flow once app review is approved.")
