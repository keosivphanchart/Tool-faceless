"""digest_due/cleanup_due/recurring_cycle_due: the pure "is it time yet"
checks behind the always-on automation loops (main.py now spawns all
three unconditionally, each polling every minute and reading its own
*_enabled/*_interval_hours setting fresh on every call) - this is what
makes flipping a switch on the Settings page take effect without a
restart, instead of only being read once at process startup.
"""
from datetime import datetime, timedelta

from faceless_pipeline.config import settings
from faceless_pipeline.modules.automation.cleanup import cleanup_due
from faceless_pipeline.modules.automation.digest import digest_due
from faceless_pipeline.modules.automation.scheduler import recurring_cycle_due


def test_digest_not_due_when_disabled(monkeypatch):
    monkeypatch.setattr(settings, "digest_enabled", False)
    monkeypatch.setattr(settings, "digest_interval_hours", 1)

    assert digest_due(datetime.utcnow() - timedelta(hours=5), datetime.utcnow()) is False


def test_digest_not_due_before_interval_elapses(monkeypatch):
    monkeypatch.setattr(settings, "digest_enabled", True)
    monkeypatch.setattr(settings, "digest_interval_hours", 24)

    assert digest_due(datetime.utcnow() - timedelta(hours=1), datetime.utcnow()) is False


def test_digest_due_once_interval_elapses(monkeypatch):
    monkeypatch.setattr(settings, "digest_enabled", True)
    monkeypatch.setattr(settings, "digest_interval_hours", 24)

    assert digest_due(datetime.utcnow() - timedelta(hours=25), datetime.utcnow()) is True


def test_digest_picks_up_a_shortened_interval_live(monkeypatch):
    """A running loop that hasn't restarted still respects a new,
    shorter DIGEST_INTERVAL_HOURS set via the dashboard mid-flight."""
    monkeypatch.setattr(settings, "digest_enabled", True)
    last_sent = datetime.utcnow() - timedelta(hours=2)

    monkeypatch.setattr(settings, "digest_interval_hours", 24)
    assert digest_due(last_sent, datetime.utcnow()) is False

    monkeypatch.setattr(settings, "digest_interval_hours", 1)
    assert digest_due(last_sent, datetime.utcnow()) is True


def test_cleanup_not_due_when_disabled(monkeypatch):
    monkeypatch.setattr(settings, "cleanup_enabled", False)
    monkeypatch.setattr(settings, "cleanup_interval_hours", 1)

    assert cleanup_due(datetime.utcnow() - timedelta(hours=5), datetime.utcnow()) is False


def test_cleanup_due_once_interval_elapses(monkeypatch):
    monkeypatch.setattr(settings, "cleanup_enabled", True)
    monkeypatch.setattr(settings, "cleanup_interval_hours", 24)

    assert cleanup_due(datetime.utcnow() - timedelta(hours=25), datetime.utcnow()) is True


def test_recurring_cycle_not_due_when_disabled(monkeypatch):
    monkeypatch.setattr(settings, "auto_trend_finder_enabled", False)
    monkeypatch.setattr(settings, "auto_trend_finder_interval_hours", 1)

    assert recurring_cycle_due(datetime.utcnow() - timedelta(hours=5), datetime.utcnow()) is False


def test_recurring_cycle_due_once_interval_elapses(monkeypatch):
    monkeypatch.setattr(settings, "auto_trend_finder_enabled", True)
    monkeypatch.setattr(settings, "auto_trend_finder_interval_hours", 24)

    assert recurring_cycle_due(datetime.utcnow() - timedelta(hours=25), datetime.utcnow()) is True


def test_recurring_cycle_flips_on_immediately_when_enabled_live(monkeypatch):
    """The core promise: toggling AUTO_TREND_FINDER_ENABLED from off to
    on, with no restart, makes the very next 60s poll tick eligible
    (once the interval has also elapsed since last_run)."""
    last_run = datetime.utcnow() - timedelta(hours=25)
    monkeypatch.setattr(settings, "auto_trend_finder_interval_hours", 24)

    monkeypatch.setattr(settings, "auto_trend_finder_enabled", False)
    assert recurring_cycle_due(last_run, datetime.utcnow()) is False

    monkeypatch.setattr(settings, "auto_trend_finder_enabled", True)
    assert recurring_cycle_due(last_run, datetime.utcnow()) is True
