"""LLM cost guardrails: tracks estimated spend per script-generation call
and refuses to start a new one once DAILY_COST_BUDGET_USD /
MONTHLY_COST_BUDGET_USD is hit. Both default to 0 (unlimited) - this is
opt-in cost protection, not a mandatory limit.

Spend is tracked in-memory only (like pipeline.py's _last_runs/_events),
so it resets on restart - a real cost dashboard would need this in the
database, but for a guardrail meant to catch "a bug is generating in a
loop" or "I forgot this was on," an in-process running total is enough.

Pricing is approximate and rounded to be a conservative (slightly high)
estimate, not a precise bill - actual provider invoices are the source
of truth for real accounting.
"""
import logging
import threading
from datetime import datetime, timedelta

from faceless_pipeline.config import settings

logger = logging.getLogger(__name__)

# USD per 1,000 tokens: (input_rate, output_rate). Ollama is free/local
# and isn't listed - estimate_cost_usd() special-cases it to always $0.
PRICING_PER_1K_TOKENS: dict[tuple[str, str], tuple[float, float]] = {
    ("anthropic", "claude-sonnet-5"): (0.003, 0.015),
    ("openai", "gpt-4o-mini"): (0.00015, 0.0006),
    ("gemini", "gemini-2.0-flash"): (0.0, 0.0),  # free tier as of writing
    ("groq", "llama-3.3-70b-versatile"): (0.00059, 0.00079),
}
# Fallback for an unrecognized (provider, model) pair - e.g. a custom
# OPENAI_MODEL/GROQ_MODEL override - assume mid-tier hosted pricing
# rather than silently reporting $0 and defeating the guardrail.
_DEFAULT_PRICING_PER_1K_TOKENS = (0.003, 0.015)

_lock = threading.Lock()
_records: list[dict] = []


class BudgetExceeded(RuntimeError):
    pass


def estimate_cost_usd(provider: str, model: str, input_tokens: int, output_tokens: int) -> float:
    if provider == "ollama":
        return 0.0
    input_rate, output_rate = PRICING_PER_1K_TOKENS.get((provider, model), _DEFAULT_PRICING_PER_1K_TOKENS)
    return (input_tokens / 1000) * input_rate + (output_tokens / 1000) * output_rate


def record_cost(provider: str, model: str, input_tokens: int, output_tokens: int) -> float:
    cost = estimate_cost_usd(provider, model, input_tokens, output_tokens)
    with _lock:
        _records.append({"at": datetime.utcnow(), "provider": provider, "model": model, "cost_usd": cost})
    return cost


def spend_since(cutoff: datetime) -> float:
    with _lock:
        return sum(r["cost_usd"] for r in _records if r["at"] >= cutoff)


def daily_spend() -> float:
    return spend_since(datetime.utcnow() - timedelta(days=1))


def monthly_spend() -> float:
    return spend_since(datetime.utcnow() - timedelta(days=30))


def spend_summary() -> dict:
    """Everything the dashboard's cost card needs in one call: current
    daily/monthly spend against their caps (0 = unlimited, same meaning
    as the settings themselves), spend broken down by day (for a trend
    chart) and by provider (for a breakdown), and how many calls that's
    based on. Same in-memory, resets-on-restart caveat as the rest of
    this module - a rough running total, not a billing record.
    """
    with _lock:
        records = list(_records)

    by_day: dict[str, float] = {}
    by_provider: dict[str, float] = {}
    for r in records:
        day = r["at"].date().isoformat()
        by_day[day] = by_day.get(day, 0.0) + r["cost_usd"]
        by_provider[r["provider"]] = by_provider.get(r["provider"], 0.0) + r["cost_usd"]

    return {
        "daily_spend_usd": round(daily_spend(), 4),
        "daily_budget_usd": settings.daily_cost_budget_usd,
        "monthly_spend_usd": round(monthly_spend(), 4),
        "monthly_budget_usd": settings.monthly_cost_budget_usd,
        "total_calls": len(records),
        "by_day": [{"date": d, "cost_usd": round(c, 4)} for d, c in sorted(by_day.items())],
        "by_provider": [
            {"provider": p, "cost_usd": round(c, 4)} for p, c in sorted(by_provider.items(), key=lambda kv: -kv[1])
        ],
    }


def check_budget() -> None:
    """Raises BudgetExceeded if a configured (non-zero) cap has already
    been hit. Call before starting a new generation, not after -
    generation itself has to have happened once to know its cost, so
    this only ever blocks the *next* call once a prior one tipped the
    running total over the cap."""
    if settings.daily_cost_budget_usd > 0:
        spent = daily_spend()
        if spent >= settings.daily_cost_budget_usd:
            raise BudgetExceeded(f"Daily LLM budget exceeded: ${spent:.4f} >= ${settings.daily_cost_budget_usd:.2f}")
    if settings.monthly_cost_budget_usd > 0:
        spent = monthly_spend()
        if spent >= settings.monthly_cost_budget_usd:
            raise BudgetExceeded(
                f"Monthly LLM budget exceeded: ${spent:.4f} >= ${settings.monthly_cost_budget_usd:.2f}"
            )
