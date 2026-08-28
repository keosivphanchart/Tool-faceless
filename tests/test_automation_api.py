"""GET /api/automation/spend: thin HTTP wrapper around
cost.spend_summary() for the Analytics page's spend card.
"""
from fastapi.testclient import TestClient

from faceless_pipeline.config import settings
from faceless_pipeline.main import app
from faceless_pipeline.modules.automation import cost as cost_module
from faceless_pipeline.modules.automation.cost import record_cost

client = TestClient(app)


def test_spend_endpoint_returns_summary(monkeypatch):
    original_records = list(cost_module._records)
    cost_module._records.clear()
    monkeypatch.setattr(settings, "daily_cost_budget_usd", 5.0)
    try:
        record_cost("anthropic", "claude-sonnet-5", input_tokens=1000, output_tokens=1000)

        resp = client.get("/api/automation/spend")

        assert resp.status_code == 200
        body = resp.json()
        assert body["daily_budget_usd"] == 5.0
        assert body["total_calls"] == 1
        assert body["daily_spend_usd"] > 0
    finally:
        cost_module._records.clear()
        cost_module._records.extend(original_records)
