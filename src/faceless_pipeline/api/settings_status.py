"""Read-only settings status for the dashboard's Settings page.

Reports whether each credential is configured, never the value itself —
credentials live in .env only, per the pipeline's non-functional
requirements, and are never sent to the frontend.
"""
from pathlib import Path

from fastapi import APIRouter

from faceless_pipeline.config import settings

router = APIRouter()


@router.get("")
def settings_status():
    return {
        "trend_seed_keywords": settings.trend_seed_keyword_list,
        "reddit_subreddits": settings.reddit_subreddit_list,
        "voice_profile": settings.kokoro_voice,
        "script_provider": settings.script_provider,
        "script_model": settings.script_model if settings.script_provider == "anthropic" else settings.ollama_model,
        "credentials_configured": {
            "youtube_api_key": bool(settings.youtube_api_key),
            "reddit_credentials": bool(settings.reddit_client_id and settings.reddit_client_secret),
            "anthropic_api_key": bool(settings.anthropic_api_key),
            "tts_fallback_api_key": bool(settings.tts_fallback_api_key),
            "pexels_api_key": bool(settings.pexels_api_key),
            "pixabay_api_key": bool(settings.pixabay_api_key),
            "telegram_bot_token": bool(settings.telegram_bot_token),
            "discord_webhook_url": bool(settings.discord_webhook_url),
            "youtube_oauth_client": Path(settings.youtube_client_secrets_file).is_file(),
            "tiktok_client_key": bool(settings.tiktok_client_key),
        },
    }
