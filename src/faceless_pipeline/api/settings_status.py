"""Read-only settings status for the dashboard's Settings page.

Reports whether each credential is configured, never the value itself —
credentials live in .env only, per the pipeline's non-functional
requirements, and are never sent to the frontend.
"""
from pathlib import Path

from fastapi import APIRouter

from faceless_pipeline.config import settings

router = APIRouter()

_SCRIPT_MODEL_BY_PROVIDER = {
    "anthropic": lambda: settings.script_model,
    "ollama": lambda: settings.ollama_model,
    "openai": lambda: settings.openai_model,
    "gemini": lambda: settings.gemini_model,
    "groq": lambda: settings.groq_model,
}


@router.get("")
def settings_status():
    return {
        "trend_seed_keywords": settings.trend_seed_keyword_list,
        "reddit_subreddits": settings.reddit_subreddit_list,
        "voice_profile": settings.kokoro_voice,
        "script_provider": settings.script_provider,
        "script_model": _SCRIPT_MODEL_BY_PROVIDER.get(settings.script_provider, lambda: settings.script_model)(),
        "credentials_configured": {
            "youtube_api_key": bool(settings.youtube_api_key),
            "reddit_credentials": bool(settings.reddit_client_id and settings.reddit_client_secret),
            "anthropic_api_key": bool(settings.anthropic_api_key),
            "openai_api_key": bool(settings.openai_api_key),
            "gemini_api_key": bool(settings.gemini_api_key),
            "groq_api_key": bool(settings.groq_api_key),
            "tts_fallback_api_key": bool(settings.tts_fallback_api_key),
            "pexels_api_key": bool(settings.pexels_api_key),
            "pixabay_api_key": bool(settings.pixabay_api_key),
            "telegram_bot_token": bool(settings.telegram_bot_token),
            "discord_webhook_url": bool(settings.discord_webhook_url),
            "youtube_oauth_client": Path(settings.youtube_client_secrets_file).is_file(),
            "tiktok_client_key": bool(settings.tiktok_client_key),
        },
        "automation": {
            "auto_generate_enabled": settings.auto_generate_enabled,
            "auto_trend_finder_enabled": settings.auto_trend_finder_enabled,
            "auto_approve_enabled": settings.auto_approve_enabled,
            "ab_test_enabled": settings.ab_test_enabled,
            "digest_enabled": settings.digest_enabled,
            "cleanup_enabled": settings.cleanup_enabled,
            "daily_cost_budget_usd": settings.daily_cost_budget_usd,
            "monthly_cost_budget_usd": settings.monthly_cost_budget_usd,
        },
    }
