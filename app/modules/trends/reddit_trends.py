"""Reddit trending posts (PRAW) as a third trend source."""
import logging

from app.config import settings

logger = logging.getLogger(__name__)


def fetch_reddit_trends(limit_per_subreddit: int = 15) -> list[dict]:
    """Returns a list of {topic, source, score} dicts pulled from the
    'hot' listing of each configured subreddit. Requires REDDIT_CLIENT_ID
    and REDDIT_CLIENT_SECRET (create an app at reddit.com/prefs/apps).
    """
    if not settings.reddit_client_id or not settings.reddit_client_secret:
        logger.info("Reddit credentials not set, skipping Reddit trend source")
        return []

    import praw

    results: list[dict] = []
    try:
        reddit = praw.Reddit(
            client_id=settings.reddit_client_id,
            client_secret=settings.reddit_client_secret,
            user_agent=settings.reddit_user_agent,
        )
        for subreddit_name in settings.reddit_subreddit_list:
            subreddit = reddit.subreddit(subreddit_name)
            for post in subreddit.hot(limit=limit_per_subreddit):
                if post.stickied:
                    continue
                # normalize upvotes to a 0-100-ish score comparable to other sources
                score = min(post.score / 50, 100.0)
                results.append({"topic": post.title, "source": "reddit", "score": score})
    except Exception:
        logger.exception("Reddit trend fetch failed")

    return results
