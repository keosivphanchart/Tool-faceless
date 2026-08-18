"""TikTok trending hashtags, via TikTok Creative Center's public trend
listing (the same data that powers ads.tiktok.com/business/creativecenter's
"Trending Hashtags" page).

This is an UNOFFICIAL, undocumented endpoint — not the Content Posting
API from Module 6, and no OAuth/API key is required to read it since the
Creative Center itself is a public marketing/research tool. That also
means it can change shape or start rate-limiting without notice; every
call here is defensive (short timeout, broad exception catch, returns []
on any failure) so a break in this source never takes down the rest of
the trend finder. Set ENABLE_TIKTOK_TRENDS=false to turn it off entirely.
"""
import logging

import requests

from faceless_pipeline.config import settings

logger = logging.getLogger(__name__)

TIKTOK_CREATIVE_CENTER_URL = "https://ads.tiktok.com/creative_radar_api/v1/popular_trend/hashtag/list"


def fetch_tiktok_trends(limit: int = 20, period_days: int = 7) -> list[dict]:
    """Returns a list of {topic, source, score} dicts for currently
    trending TikTok hashtags in the configured country."""
    if not settings.enable_tiktok_trends:
        return []

    results: list[dict] = []
    try:
        response = requests.get(
            TIKTOK_CREATIVE_CENTER_URL,
            params={
                "page": 1,
                "limit": limit,
                "period": period_days,
                "country_code": settings.tiktok_trending_country,
                "sort_by": "popular",
            },
            headers={"User-Agent": "Mozilla/5.0 (faceless-pipeline trend research)"},
            timeout=15,
        )
        response.raise_for_status()
        data = response.json()

        items = (data.get("data") or {}).get("list", [])
        for item in items:
            hashtag = item.get("hashtag_name")
            if not hashtag:
                continue
            # TikTok reports a popularity index and rank; normalize rank
            # into a 0-100-ish score comparable to the other sources.
            rank = item.get("rank", limit)
            score = max(100.0 - (rank * (100.0 / max(limit, 1))), 0.0)
            results.append({"topic": f"#{hashtag}", "source": "tiktok", "score": score})
    except Exception:
        logger.exception(
            "TikTok trend fetch failed (this endpoint is unofficial and may have "
            "changed shape — set ENABLE_TIKTOK_TRENDS=false to disable it)"
        )

    return results
