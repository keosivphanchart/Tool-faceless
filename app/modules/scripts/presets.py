"""Style presets and length variants for the script generator."""

STYLE_PRESETS: dict[str, str] = {
    "listicle": (
        "Write it as a countdown/listicle (e.g. '5 things...'). Body should "
        "read as distinct numbered beats, each punchy enough to stand alone."
    ),
    "story": (
        "Write it as a first/second-person mini narrative with a clear "
        "beginning, tension, and resolution. Personal, anecdotal tone."
    ),
    "explainer": (
        "Write it as a clear, direct explainer. Prioritize clarity and a "
        "single strong insight over cleverness."
    ),
    "hot_take": (
        "Write it as a contrarian hot take. Open with a claim that "
        "challenges common belief, then back it up fast."
    ),
}

# Approximate spoken word counts at ~2.5 words/sec, used to size the body.
LENGTH_VARIANTS: dict[str, dict] = {
    "15s": {"seconds": 15, "target_words": 35},
    "30s": {"seconds": 30, "target_words": 75},
    "60s": {"seconds": 60, "target_words": 150},
}

DEFAULT_STYLE = "explainer"
DEFAULT_LENGTH = "30s"
