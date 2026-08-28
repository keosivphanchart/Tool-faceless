"""LLM cost guardrails: estimate_cost_usd/record_cost/check_budget.
Both DAILY_COST_BUDGET_USD and MONTHLY_COST_BUDGET_USD default to 0
(unlimited) - check_budget() must be a no-op until one is deliberately
set non-zero.
"""
import pytest

from faceless_pipeline.config import settings
from faceless_pipeline.modules.automation import cost as cost_module
from faceless_pipeline.modules.automation.cost import (
    BudgetExceeded,
    check_budget,
    daily_spend,
    estimate_cost_usd,
    record_cost,
    spend_summary,
)


@pytest.fixture(autouse=True)
def _reset_cost_records():
    original_records = list(cost_module._records)
    original_daily = settings.daily_cost_budget_usd
    original_monthly = settings.monthly_cost_budget_usd
    cost_module._records.clear()
    yield
    cost_module._records.clear()
    cost_module._records.extend(original_records)
    settings.daily_cost_budget_usd = original_daily
    settings.monthly_cost_budget_usd = original_monthly


def test_ollama_is_always_free():
    assert estimate_cost_usd("ollama", "llama3.2", input_tokens=1_000_000, output_tokens=1_000_000) == 0.0


def test_known_provider_model_uses_its_real_rate():
    cost = estimate_cost_usd("anthropic", "claude-sonnet-5", input_tokens=1000, output_tokens=1000)
    assert cost == pytest.approx(0.003 + 0.015)


def test_unrecognized_model_falls_back_to_default_pricing_not_zero():
    cost = estimate_cost_usd("openai", "some-future-model-not-in-the-table", input_tokens=1000, output_tokens=1000)
    assert cost > 0


def test_record_cost_accumulates_into_daily_spend():
    record_cost("anthropic", "claude-sonnet-5", input_tokens=1000, output_tokens=1000)
    record_cost("anthropic", "claude-sonnet-5", input_tokens=1000, output_tokens=1000)

    assert daily_spend() == pytest.approx(2 * (0.003 + 0.015))


def test_check_budget_is_a_noop_when_unlimited():
    settings.daily_cost_budget_usd = 0
    settings.monthly_cost_budget_usd = 0
    record_cost("anthropic", "claude-sonnet-5", input_tokens=1_000_000, output_tokens=1_000_000)

    check_budget()  # must not raise


def test_check_budget_raises_once_daily_cap_is_hit():
    settings.daily_cost_budget_usd = 0.01
    settings.monthly_cost_budget_usd = 0
    record_cost("anthropic", "claude-sonnet-5", input_tokens=1000, output_tokens=1000)  # ~$0.018, over the cap

    with pytest.raises(BudgetExceeded, match="Daily"):
        check_budget()


def test_check_budget_raises_once_monthly_cap_is_hit():
    settings.daily_cost_budget_usd = 0
    settings.monthly_cost_budget_usd = 0.01
    record_cost("anthropic", "claude-sonnet-5", input_tokens=1000, output_tokens=1000)

    with pytest.raises(BudgetExceeded, match="Monthly"):
        check_budget()


def test_check_budget_passes_when_under_cap():
    settings.daily_cost_budget_usd = 100.0
    settings.monthly_cost_budget_usd = 0
    record_cost("anthropic", "claude-sonnet-5", input_tokens=1000, output_tokens=1000)

    check_budget()  # must not raise


def test_spend_summary_with_no_calls_is_all_zero():
    settings.daily_cost_budget_usd = 5.0
    settings.monthly_cost_budget_usd = 50.0

    summary = spend_summary()

    assert summary["daily_spend_usd"] == 0
    assert summary["daily_budget_usd"] == 5.0
    assert summary["monthly_spend_usd"] == 0
    assert summary["monthly_budget_usd"] == 50.0
    assert summary["total_calls"] == 0
    assert summary["by_day"] == []
    assert summary["by_provider"] == []


def test_spend_summary_aggregates_by_provider_and_counts_calls():
    record_cost("anthropic", "claude-sonnet-5", input_tokens=1000, output_tokens=1000)
    record_cost("anthropic", "claude-sonnet-5", input_tokens=1000, output_tokens=1000)
    record_cost("openai", "gpt-4o-mini", input_tokens=1000, output_tokens=1000)

    summary = spend_summary()

    assert summary["total_calls"] == 3
    providers = {p["provider"]: p["cost_usd"] for p in summary["by_provider"]}
    # spend_summary() rounds to 4dp (a display concern, not precise
    # accounting - see its docstring), so compare against the same rounding.
    assert providers["anthropic"] == pytest.approx(round(2 * (0.003 + 0.015), 4))
    assert providers["openai"] == pytest.approx(round(0.00015 + 0.0006, 4))
    # sorted by cost descending
    assert summary["by_provider"][0]["provider"] == "anthropic"


def test_spend_summary_groups_by_calendar_day():
    from datetime import datetime, timedelta

    with cost_module._lock:
        cost_module._records.append({"at": datetime.utcnow() - timedelta(days=3), "provider": "anthropic", "model": "claude-sonnet-5", "cost_usd": 1.0})
        cost_module._records.append({"at": datetime.utcnow(), "provider": "anthropic", "model": "claude-sonnet-5", "cost_usd": 2.0})

    summary = spend_summary()

    assert len(summary["by_day"]) == 2
    assert sum(d["cost_usd"] for d in summary["by_day"]) == pytest.approx(3.0)
    # sorted ascending by date, so the 3-days-ago entry comes first
    assert summary["by_day"][0]["date"] <= summary["by_day"][1]["date"]


def test_spend_summary_daily_budget_zero_means_unlimited():
    settings.daily_cost_budget_usd = 0

    summary = spend_summary()

    assert summary["daily_budget_usd"] == 0
