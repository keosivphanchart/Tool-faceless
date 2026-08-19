"""check_health(): cheap, no-network checks for whether things a
pipeline run will need are actually present. Must only flag a problem
for something current settings say *should* be configured.
"""
from pathlib import Path

from faceless_pipeline.config import settings
from faceless_pipeline.modules.automation.health import check_health


def test_healthy_when_ffmpeg_present_and_provider_key_set(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "ffmpeg_binary", "true")  # /bin/true - always on PATH
    monkeypatch.setattr(settings, "ffprobe_binary", "true")
    monkeypatch.setattr(settings, "script_provider", "anthropic")
    monkeypatch.setattr(settings, "anthropic_api_key", "sk-test")
    monkeypatch.setattr(settings, "tiktok_client_key", "")
    monkeypatch.setattr(settings, "youtube_client_secrets_file", str(tmp_path / "does_not_exist.json"))

    assert check_health() == []


def test_flags_missing_ffmpeg_binary(monkeypatch):
    monkeypatch.setattr(settings, "ffmpeg_binary", "definitely-not-a-real-binary-xyz")
    monkeypatch.setattr(settings, "ffprobe_binary", "true")
    monkeypatch.setattr(settings, "script_provider", "ollama")

    problems = check_health()

    assert any("ffmpeg" in p for p in problems)


def test_flags_missing_api_key_for_the_active_provider(monkeypatch):
    monkeypatch.setattr(settings, "ffmpeg_binary", "true")
    monkeypatch.setattr(settings, "ffprobe_binary", "true")
    monkeypatch.setattr(settings, "script_provider", "openai")
    monkeypatch.setattr(settings, "openai_api_key", "")

    problems = check_health()

    assert any("OPENAI_API_KEY" in p for p in problems)


def test_does_not_flag_missing_key_for_an_inactive_provider(monkeypatch):
    monkeypatch.setattr(settings, "ffmpeg_binary", "true")
    monkeypatch.setattr(settings, "ffprobe_binary", "true")
    monkeypatch.setattr(settings, "script_provider", "ollama")  # ollama needs no key
    monkeypatch.setattr(settings, "openai_api_key", "")  # unrelated - should not be flagged

    problems = check_health()

    assert not any("OPENAI_API_KEY" in p for p in problems)


def test_flags_unauthorized_youtube_when_client_secrets_exist_but_no_token(tmp_path, monkeypatch):
    secrets_file = tmp_path / "client_secret.json"
    secrets_file.write_text("{}")
    token_file = tmp_path / "token.json"  # deliberately not created

    monkeypatch.setattr(settings, "ffmpeg_binary", "true")
    monkeypatch.setattr(settings, "ffprobe_binary", "true")
    monkeypatch.setattr(settings, "script_provider", "ollama")
    monkeypatch.setattr(settings, "youtube_client_secrets_file", str(secrets_file))
    monkeypatch.setattr(settings, "youtube_token_file", str(token_file))

    problems = check_health()

    assert any("YouTube" in p for p in problems)


def test_flags_unauthorized_tiktok_when_credentials_exist_but_no_token(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "ffmpeg_binary", "true")
    monkeypatch.setattr(settings, "ffprobe_binary", "true")
    monkeypatch.setattr(settings, "script_provider", "ollama")
    monkeypatch.setattr(settings, "tiktok_client_key", "key")
    monkeypatch.setattr(settings, "tiktok_client_secret", "secret")
    monkeypatch.setattr(settings, "tiktok_token_file", str(tmp_path / "no_token.json"))

    problems = check_health()

    assert any("TikTok" in p for p in problems)
