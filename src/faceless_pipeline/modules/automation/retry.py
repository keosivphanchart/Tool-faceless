"""Retry-with-backoff for pipeline stages that fail on transient errors
(network blips, provider rate limits) rather than deterministic ones. A
failed script/video generation used to just sit there until a human
noticed and manually clicked regenerate — this gives it a few automatic
shots first.
"""
import logging
import time

from faceless_pipeline.config import settings

logger = logging.getLogger(__name__)


def run_with_retries(fn, *args, max_attempts: int | None = None, backoff_seconds: int | None = None, **kwargs):
    """Calls fn(*args, **kwargs), retrying on exception with exponential
    backoff (backoff_seconds, then 2x, 4x, ...) up to max_attempts
    total tries, then re-raises the last exception.

    ValueError is never retried: throughout this codebase it's used
    specifically for deterministic business-logic failures (duplicate
    topic, video not found, wrong status) that will fail identically on
    every attempt — retrying would only add delay, not a chance of
    success.
    """
    max_attempts = max_attempts if max_attempts is not None else settings.retry_max_attempts
    backoff_seconds = backoff_seconds if backoff_seconds is not None else settings.retry_backoff_seconds

    last_exc: Exception | None = None
    for attempt in range(1, max_attempts + 1):
        try:
            return fn(*args, **kwargs)
        except ValueError:
            raise
        except Exception as exc:
            last_exc = exc
            if attempt < max_attempts:
                delay = backoff_seconds * (2 ** (attempt - 1))
                logger.warning(
                    "Attempt %d/%d of %s failed (%s), retrying in %ds",
                    attempt, max_attempts, getattr(fn, "__name__", fn), exc, delay,
                )
                time.sleep(delay)

    assert last_exc is not None  # loop always runs >=1 time, so this only executes after >=1 failure
    raise last_exc
