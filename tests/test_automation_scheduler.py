"""run_recurring_cycle(): the synchronous tick body of the recurring
automation loop (AUTO_TREND_FINDER_ENABLED) - finds trends, then also
auto-generates from them if AUTO_GENERATE_ENABLED is on. The async sleep
loop itself isn't meaningfully unit-testable (it's a timing loop), but
this tick function is exactly what it calls every interval.
"""
from unittest.mock import patch

from faceless_pipeline.config import settings
from faceless_pipeline.modules.automation.scheduler import run_recurring_cycle


def test_tick_runs_trend_finder(db_session):
    original = settings.auto_generate_enabled
    settings.auto_generate_enabled = False
    try:
        with patch("faceless_pipeline.modules.trends.run.run_trend_finder", return_value=[]) as mock_trends:
            run_recurring_cycle()
        mock_trends.assert_called_once()
    finally:
        settings.auto_generate_enabled = original


def test_tick_also_auto_generates_when_enabled(db_session):
    original = settings.auto_generate_enabled
    settings.auto_generate_enabled = True
    try:
        with patch("faceless_pipeline.modules.trends.run.run_trend_finder", return_value=[]), patch(
            "faceless_pipeline.modules.automation.run.auto_generate_from_trends", return_value=[]
        ) as mock_generate:
            run_recurring_cycle()
        mock_generate.assert_called_once()
    finally:
        settings.auto_generate_enabled = original


def test_tick_skips_auto_generate_when_disabled(db_session):
    original = settings.auto_generate_enabled
    settings.auto_generate_enabled = False
    try:
        with patch("faceless_pipeline.modules.trends.run.run_trend_finder", return_value=[]), patch(
            "faceless_pipeline.modules.automation.run.auto_generate_from_trends"
        ) as mock_generate:
            run_recurring_cycle()
        mock_generate.assert_not_called()
    finally:
        settings.auto_generate_enabled = original


def test_tick_survives_a_trend_finder_failure_without_raising(db_session):
    with patch("faceless_pipeline.modules.trends.run.run_trend_finder", side_effect=RuntimeError("boom")):
        run_recurring_cycle()  # must not raise
