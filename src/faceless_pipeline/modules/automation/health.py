"""Proactive integration health checks — periodic, cheap checks (no
network calls, no cost) for whether things a pipeline run will need are
actually present, so a missing ffmpeg binary or an un-authorized
platform surfaces as a dashboard toast before a real run trips over it
partway through, not during one.
"""
import asyncio
import logging
import shutil
from pathlib import Path

from faceless_pipeline.config import settings

logger = logging.getLogger(__name__)

_PROVIDER_KEY_SETTING = {
    "anthropic": "anthropic_api_key",
    "openai": "openai_api_key",
    "gemini": "gemini_api_key",
    "groq": "groq_api_key",
    # ollama needs no key - can't cheaply check reachability without a
    # network call, which this deliberately avoids (no cost, no traffic).
}


def check_health() -> list[str]:
    """Returns human-readable problems found; empty = healthy. Only
    flags things current settings say *should* be configured — e.g.
    never complains about a missing TikTok token when TikTok isn't
    configured at all."""
    problems = []

    if not shutil.which(settings.ffmpeg_binary):
        problems.append(f"ffmpeg binary '{settings.ffmpeg_binary}' not found on PATH")
    if not shutil.which(settings.ffprobe_binary):
        problems.append(f"ffprobe binary '{settings.ffprobe_binary}' not found on PATH")

    key_setting = _PROVIDER_KEY_SETTING.get(settings.script_provider)
    if key_setting and not getattr(settings, key_setting):
        problems.append(f"SCRIPT_PROVIDER={settings.script_provider} but {key_setting.upper()} is not set")

    if Path(settings.youtube_client_secrets_file).exists() and not Path(settings.youtube_token_file).exists():
        problems.append("YouTube OAuth client configured but not yet authorized (no cached token)")

    if (
        settings.tiktok_client_key
        and settings.tiktok_client_secret
        and not Path(settings.tiktok_token_file).exists()
    ):
        problems.append(
            "TikTok configured but not yet authorized — run "
            "`python -m faceless_pipeline.modules.publisher.tiktok` once"
        )

    return problems


async def run_health_check_loop() -> None:
    from faceless_pipeline.api.pipeline import record_run

    interval_seconds = max(settings.health_check_interval_minutes, 1) * 60
    last_problems: set[str] = set()

    while True:
        try:
            problems = set(await asyncio.to_thread(check_health))
            for problem in problems - last_problems:
                record_run("health", "error", problem)
            for resolved in last_problems - problems:
                record_run("health", "success", f"resolved: {resolved}")
            last_problems = problems
        except Exception:
            logger.exception("Health check loop tick failed")
        await asyncio.sleep(interval_seconds)
