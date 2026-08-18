"""Pull related/rising queries from Google Trends for seed keywords."""
import logging

logger = logging.getLogger(__name__)


def fetch_google_trends(seed_keywords: list[str]) -> list[dict]:
    """Returns a list of {topic, source, score} dicts.

    Uses pytrends (unofficial Google Trends API client). Google Trends
    rate-limits aggressively, so seed_keywords should be a handful of
    terms, and this should not be called more than once every few minutes.
    """
    try:
        from pytrends.request import TrendReq
    except ImportError:
        logger.info("pytrends not installed (pip install -e '.[trends]'), skipping Google Trends source")
        return []

    results: list[dict] = []
    pytrends = TrendReq(hl="en-US", tz=360)

    for keyword in seed_keywords:
        try:
            pytrends.build_payload([keyword], timeframe="now 7-d")

            related = pytrends.related_queries().get(keyword, {})
            for kind, score_base in (("top", 50), ("rising", 80)):
                df = related.get(kind)
                if df is None:
                    continue
                for _, row in df.iterrows():
                    query = str(row["query"])
                    raw_value = row.get("value", 0)
                    # "rising" queries report a percentage-increase value
                    # (or 'Breakout'); normalize both to a 0-100-ish score.
                    if isinstance(raw_value, str):
                        score = 100.0
                    else:
                        score = min(float(raw_value), 1000) / 10 + score_base
                    results.append({"topic": query, "source": "google_trends", "score": score})
        except Exception:
            logger.exception("Google Trends fetch failed for keyword=%s", keyword)

    return results
