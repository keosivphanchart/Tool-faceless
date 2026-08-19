"""run_with_retries(): auto-retries a transient failure with backoff,
but never retries a ValueError (this codebase's convention for
deterministic business-logic failures that would fail identically every
time - duplicate topic, not found, wrong status).
"""
from unittest.mock import patch

import pytest

from faceless_pipeline.modules.automation.retry import run_with_retries


def test_succeeds_on_first_try_without_retrying():
    calls = []

    def fn():
        calls.append(1)
        return "ok"

    with patch("time.sleep") as mock_sleep:
        result = run_with_retries(fn, max_attempts=3, backoff_seconds=1)

    assert result == "ok"
    assert len(calls) == 1
    mock_sleep.assert_not_called()


def test_retries_transient_failures_up_to_max_attempts_then_succeeds():
    calls = []

    def fn():
        calls.append(1)
        if len(calls) < 3:
            raise RuntimeError("transient")
        return "ok"

    with patch("time.sleep") as mock_sleep:
        result = run_with_retries(fn, max_attempts=5, backoff_seconds=1)

    assert result == "ok"
    assert len(calls) == 3
    assert mock_sleep.call_count == 2  # backoff before attempt 2 and attempt 3


def test_uses_exponential_backoff_delays():
    def fn():
        raise RuntimeError("always fails")

    with patch("time.sleep") as mock_sleep, pytest.raises(RuntimeError):
        run_with_retries(fn, max_attempts=4, backoff_seconds=10)

    delays = [call.args[0] for call in mock_sleep.call_args_list]
    assert delays == [10, 20, 40]


def test_gives_up_after_max_attempts_and_reraises_last_exception():
    def fn():
        raise RuntimeError("persistent failure")

    with patch("time.sleep"), pytest.raises(RuntimeError, match="persistent failure"):
        run_with_retries(fn, max_attempts=3, backoff_seconds=1)


def test_value_error_is_never_retried():
    calls = []

    def fn():
        calls.append(1)
        raise ValueError("duplicate topic")

    with patch("time.sleep") as mock_sleep, pytest.raises(ValueError, match="duplicate topic"):
        run_with_retries(fn, max_attempts=5, backoff_seconds=1)

    assert len(calls) == 1
    mock_sleep.assert_not_called()


def test_passes_through_args_and_kwargs():
    def fn(a, b, c=None):
        return (a, b, c)

    result = run_with_retries(fn, 1, 2, max_attempts=1, backoff_seconds=1, c=3)

    assert result == (1, 2, 3)
