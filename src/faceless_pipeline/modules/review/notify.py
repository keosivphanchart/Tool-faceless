"""Telegram / Discord notifications: a new video ready for review, and
(see automation/digest.py) periodic summary digests — both send through
the same two channels, so the actual HTTP posting lives here once.
"""
import logging

import requests

from faceless_pipeline.config import settings

logger = logging.getLogger(__name__)


def send_notification(message: str) -> None:
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


def notify_video_ready(video_id: int, topic: str) -> None:
    send_notification(f"New video ready for review: '{topic}' (id={video_id})")
