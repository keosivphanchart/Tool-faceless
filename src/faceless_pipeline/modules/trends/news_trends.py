"""News headlines as a trend source, via NewsAPI.org's top-headlines
endpoint. Complements Google Trends/YouTube/Reddit with topics that are
breaking right now rather than already trending in search/social.
"""
import logging

import requests

from faceless_pipeline.config import settings

logger = logging.getLogger(__name__)

NEWSAPI_URL = "https://newsapi.org/v2/top-headlines"


def fetch_news_trends(page_size: int = 20) -> list[dict]:
    """Returns a list of {topic, source, score} dicts from top headlines
    in the configured country/category. Requires NEWSAPI_KEY; returns []
    silently if unset so the rest of the trend finder can still run.
    """
    if not settings.newsapi_key:
        logger.info("NEWSAPI_KEY not set, skipping news trend source")
        return []

    results: list[dict] = []
    try:
        params = {
            "apiKey": settings.newsapi_key,
            "country": settings.news_country,
            "pageSize": page_size,
        }
        if settings.news_category:
            params["category"] = settings.news_category

        response = requests.get(NEWSAPI_URL, params=params, timeout=30)
        response.raise_for_status()
        data = response.json()

        articles = data.get("articles", [])
        total = len(articles) or 1
        for rank, article in enumerate(articles):
            title = article.get("title")
            if not title:
                continue
            # Higher-ranked headlines (as returned by NewsAPI) score higher;
            # comparable range to the other sources' 0-100-ish scores.
            score = 100.0 * (total - rank) / total
            results.append({"topic": title, "source": "news", "score": score})
    except Exception:
        logger.exception("News trend fetch failed")

    return results
