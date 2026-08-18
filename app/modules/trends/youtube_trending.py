"""Optional YouTube trending video pull."""
import logging

from app.config import settings

logger = logging.getLogger(__name__)


def fetch_youtube_trending(region_code: str = "US", max_results: int = 25) -> list[dict]:
    """Returns a list of {topic, source, score} dicts from YouTube's
    mostPopular chart. Requires YOUTUBE_API_KEY. Returns [] silently if
    no key is configured so the rest of the trend finder can still run.
    """
    if not settings.youtube_api_key:
        logger.info("YOUTUBE_API_KEY not set, skipping YouTube trending source")
        return []

    from googleapiclient.discovery import build

    results: list[dict] = []
    try:
        youtube = build("youtube", "v3", developerKey=settings.youtube_api_key)
        request = youtube.videos().list(
            part="snippet,statistics",
            chart="mostPopular",
            regionCode=region_code,
            maxResults=max_results,
        )
        response = request.execute()
        for item in response.get("items", []):
            title = item["snippet"]["title"]
            views = int(item.get("statistics", {}).get("viewCount", 0))
            # log-scale views into a comparable score range with Trends output
            score = min(views / 10000, 100.0)
            results.append({"topic": title, "source": "youtube", "score": score})
    except Exception:
        logger.exception("YouTube trending fetch failed")

    return results
