"""Voice profile selection for Module 3.

Kokoro (https://github.com/hexgrad/kokoro) ships a fixed set of named
voices. This is a curated subset good for narration; extend as needed.
"""

VOICE_PROFILES: dict[str, dict] = {
    "af_heart": {"label": "Heart (US female, warm)", "lang": "en-us"},
    "af_bella": {"label": "Bella (US female, energetic)", "lang": "en-us"},
    "am_michael": {"label": "Michael (US male, deep)", "lang": "en-us"},
    "bf_emma": {"label": "Emma (UK female)", "lang": "en-gb"},
    "bm_george": {"label": "George (UK male)", "lang": "en-gb"},
}

DEFAULT_VOICE = "af_heart"


def resolve_voice(voice_id: str | None) -> str:
    if voice_id and voice_id in VOICE_PROFILES:
        return voice_id
    return DEFAULT_VOICE
