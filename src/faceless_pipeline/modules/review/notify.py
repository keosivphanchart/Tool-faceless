"""Telegram / Discord notification when a new video is ready for review."""
import logging

import requests

from faceless_pipeline.config import settings

logger = logging.getLogger(__name__)


def notify_video_ready(video_id: int, topic: str) -> None:
    message = f"New video ready for review: '{topic}' (id={video_id})"

    if settings.telegram_bot_token and settings.telegram_chat_id:
        try:
            requests.post(
                f"https://api.telegram.org/bot{settings.telegram_bot_token}/sendMessage",
                json={"chat_id": settings.telegram_chat_id, "text": message},
                timeout=15,
            )
        except Exception:
            logger.exception("Telegram notification failed")

    if settings.discord_webhook_url:
        try:
            requests.post(settings.discord_webhook_url, json={"content": message}, timeout=15)
        except Exception:
            logger.exception("Discord notification failed")

    if not settings.telegram_bot_token and not settings.discord_webhook_url:
        logger.info("No Telegram/Discord configured; skipping notification: %s", message)
