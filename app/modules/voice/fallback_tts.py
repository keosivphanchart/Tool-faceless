"""Fallback to a paid TTS API for scripts where self-hosted Kokoro quality
isn't good enough. Defaults to ElevenLabs; swap the request body/endpoint
if TTS_FALLBACK_PROVIDER is a different vendor.
"""
import logging
from pathlib import Path

import requests

from app.config import settings

logger = logging.getLogger(__name__)

ELEVENLABS_TTS_URL = "https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"


def synthesize_fallback(text: str, out_path: str, voice_id: str = "21m00Tcm4TlvDq8ikWAM") -> str:
    if settings.tts_fallback_provider != "elevenlabs":
        raise NotImplementedError(
            f"No fallback TTS integration for provider '{settings.tts_fallback_provider}'. "
            "Add one alongside this function."
        )
    if not settings.tts_fallback_api_key:
        raise RuntimeError("TTS_FALLBACK_API_KEY is not set")

    Path(out_path).parent.mkdir(parents=True, exist_ok=True)

    response = requests.post(
        ELEVENLABS_TTS_URL.format(voice_id=voice_id),
        headers={"xi-api-key": settings.tts_fallback_api_key, "Content-Type": "application/json"},
        json={"text": text, "model_id": "eleven_multilingual_v2"},
        timeout=60,
    )
    response.raise_for_status()

    with open(out_path, "wb") as f:
        f.write(response.content)

    logger.info("Fallback TTS synthesized via %s -> %s", settings.tts_fallback_provider, out_path)
    return out_path
