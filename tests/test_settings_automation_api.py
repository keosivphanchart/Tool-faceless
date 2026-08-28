"""PATCH /api/settings/automation: flips one or more automation flags
live (no restart), the dashboard-facing side of the always-on loops
tested against directly in test_automation_live_toggle.py.
"""
from fastapi.testclient import TestClient

from faceless_pipeline.config import settings
from faceless_pipeline.main import app

client = TestClient(app)


def test_patch_flips_a_single_flag_and_leaves_others_untouched(monkeypatch):
    monkeypatch.setattr(settings, "auto_generate_enabled", False)
    monkeypatch.setattr(settings, "auto_approve_enabled", False)

    resp = client.patch("/api/settings/automation", json={"auto_generate_enabled": True})

    assert resp.status_code == 200
    body = resp.json()
    assert body["auto_generate_enabled"] is True
    assert body["auto_approve_enabled"] is False
    assert settings.auto_generate_enabled is True


def test_patch_flips_multiple_flags_in_one_call(monkeypatch):
    monkeypatch.setattr(settings, "digest_enabled", False)
    monkeypatch.setattr(settings, "cleanup_enabled", False)

    resp = client.patch("/api/settings/automation", json={"digest_enabled": True, "cleanup_enabled": True})

    assert resp.status_code == 200
    body = resp.json()
    assert body["digest_enabled"] is True
    assert body["cleanup_enabled"] is True


def test_patch_with_no_fields_is_a_noop(monkeypatch):
    monkeypatch.setattr(settings, "ab_test_enabled", True)

    resp = client.patch("/api/settings/automation", json={})

    assert resp.status_code == 200
    assert resp.json()["ab_test_enabled"] is True


def test_get_settings_reflects_a_prior_patch(monkeypatch):
    monkeypatch.setattr(settings, "auto_trend_finder_enabled", False)

    client.patch("/api/settings/automation", json={"auto_trend_finder_enabled": True})
    resp = client.get("/api/settings")

    assert resp.status_code == 200
    assert resp.json()["automation"]["auto_trend_finder_enabled"] is True
