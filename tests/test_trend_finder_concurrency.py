"""Regression test: the 5 trend sources must be fetched concurrently, not
sequentially.

Each source is an independent, blocking network call with its own
timeout (up to 30s). Run one after another, the worst-case wait is the
*sum* of all five; a single slow or timed-out source used to delay every
source queued behind it. Fetching them via a ThreadPoolExecutor bounds
the wait to the slowest single source instead.

Also guards a real bug introduced while making this fix: building the
fetcher list once at module-import time bound directly to the original
function objects, which broke `unittest.mock.patch.object(module, name)`
— patching the module attribute afterward didn't reach a reference
already captured in an import-time list. The fetcher list must be built
fresh inside the function on every call.
"""
import time
from unittest.mock import patch

from faceless_pipeline.models import Trend
from faceless_pipeline.modules.trends import run as run_mod


def _slow(seconds, result):
    def _fetch(*args, **kwargs):
        time.sleep(seconds)
        return result

    return _fetch


def _failing(*args, **kwargs):
    raise RuntimeError("simulated unexpected failure")


def test_sources_fetched_concurrently_not_sequentially(db_session):
    with patch.object(run_mod, "fetch_google_trends", _slow(0.3, [])), patch.object(
        run_mod, "fetch_youtube_trending", _slow(0.3, [])
    ), patch.object(run_mod, "fetch_reddit_trends", _slow(0.3, [])), patch.object(
        run_mod, "fetch_tiktok_trends", _slow(0.3, [])
    ), patch.object(run_mod, "fetch_news_trends", _slow(0.3, [])):
        start = time.perf_counter()
        run_mod._fetch_all_sources()
        elapsed = time.perf_counter() - start

    # Concurrent: ~0.3s (the slowest single source). Sequential: ~1.5s
    # (five sources x 0.3s each). Generous margin for test-runner jitter.
    assert elapsed < 0.8, f"took {elapsed:.2f}s — sources are not running concurrently"


def test_a_failing_source_does_not_drop_the_others(db_session):
    with patch.object(
        run_mod, "fetch_google_trends", _slow(0, [{"topic": "g1", "source": "google_trends", "score": 10}])
    ), patch.object(run_mod, "fetch_youtube_trending", _failing), patch.object(
        run_mod, "fetch_reddit_trends", _slow(0, [{"topic": "r1", "source": "reddit", "score": 20}])
    ), patch.object(run_mod, "fetch_tiktok_trends", _slow(0, [])), patch.object(
        run_mod, "fetch_news_trends", _slow(0, [])
    ):
        candidates = run_mod._fetch_all_sources()

    assert sorted(c["topic"] for c in candidates) == ["g1", "r1"]


def test_patched_fetchers_are_actually_used_end_to_end(db_session):
    """Catches the import-time-list bug directly: run_trend_finder() must
    persist trends from patched sources, not the real network-calling
    ones."""
    with patch.object(
        run_mod, "fetch_google_trends", _slow(0, [{"topic": "patched topic", "source": "google_trends", "score": 99}])
    ), patch.object(run_mod, "fetch_youtube_trending", _slow(0, [])), patch.object(
        run_mod, "fetch_reddit_trends", _slow(0, [])
    ), patch.object(run_mod, "fetch_tiktok_trends", _slow(0, [])), patch.object(
        run_mod, "fetch_news_trends", _slow(0, [])
    ), patch.object(run_mod, "SessionLocal", return_value=db_session):
        # SessionLocal is patched too so run_trend_finder() operates on
        # the same in-memory db_session the test can inspect afterward.
        run_mod.run_trend_finder()

    topics = [t.topic for t in db_session.query(Trend).all()]
    assert topics == ["patched topic"]
