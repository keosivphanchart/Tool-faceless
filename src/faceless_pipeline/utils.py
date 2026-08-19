from datetime import datetime, timezone


def normalize_to_naive_utc(value: datetime | None) -> datetime | None:
    """Every datetime in this codebase (Trend.created_at,
    Performance.pulled_at, datetime.utcnow() itself) is naive UTC, but a
    browser client sends `new Date(...).toISOString()`, which is always
    timezone-aware (a trailing "Z"). Comparing an aware and a naive
    datetime raises TypeError - normalize once, at every request model
    that accepts a datetime from the dashboard, rather than at each
    comparison site downstream. See review/api.py's ApproveRequest for
    the bug this was originally found fixing.
    """
    if value is not None and value.tzinfo is not None:
        return value.astimezone(timezone.utc).replace(tzinfo=None)
    return value
