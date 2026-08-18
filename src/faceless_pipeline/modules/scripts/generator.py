"""Module 2: Script generator.

Generates a hook / promise / body / payoff / CTA structured script via the
Claude API, with style presets, length variants, feedback-driven
regeneration, and per-topic history to avoid generating the same script
twice.
"""
import json
import logging

from sqlalchemy.orm import Session

from faceless_pipeline.config import settings
from faceless_pipeline.models import Script, Trend
from faceless_pipeline.modules.scripts.presets import (
    DEFAULT_LENGTH,
    DEFAULT_STYLE,
    LENGTH_VARIANTS,
    STYLE_PRESETS,
)

logger = logging.getLogger(__name__)

STORYBOARD_BEATS = ["hook", "promise", "body", "payoff", "cta"]

SYSTEM_PROMPT = """You are a short-form video scriptwriter and visual \
director for faceless content channels (YouTube Shorts / TikTok / \
Reels). You write tight, high-retention scripts AND plan what's on \
screen for each beat, since these videos have no host to look at — the \
visual has to carry the moment on its own.

Always respond with ONLY a JSON object with exactly these keys:
{
  "hook": "...",     // first 1-2 lines, must earn the next 3 seconds
  "promise": "...",  // what the viewer gets if they keep watching
  "body": "...",     // the core content, delivering on the promise
  "payoff": "...",   // the satisfying conclusion / insight
  "cta": "...",      // one short call to action
  "storyboard": [    // exactly 5 shots, one per beat above, in order
    {
      "beat": "hook",         // one of: hook, promise, body, payoff, cta
      "visual": "...",        // one concrete sentence: what's on screen during this beat
      "keywords": ["...", "..."]  // 2-3 short search terms for stock footage matching that visual
    }
    // ... one entry each for promise, body, payoff, cta, same shape, same order
  ]
}
No markdown, no commentary, no code fences — raw JSON only."""


def _build_user_prompt(topic: str, style: str, length_variant: str, feedback_note: str | None = None) -> str:
    style_instruction = STYLE_PRESETS.get(style, STYLE_PRESETS[DEFAULT_STYLE])
    length_spec = LENGTH_VARIANTS.get(length_variant, LENGTH_VARIANTS[DEFAULT_LENGTH])

    prompt = (
        f"Topic: {topic}\n\n"
        f"Style: {style_instruction}\n\n"
        f"Target length: ~{length_spec['seconds']}s spoken "
        f"(~{length_spec['target_words']} words total across all fields)."
    )

    if feedback_note:
        prompt += (
            f"\n\nThis is a REWRITE. Here is feedback on the previous draft "
            f"that you must address:\n{feedback_note}"
        )

    return prompt


_STOPWORDS = {"the", "a", "an", "of", "to", "in", "for", "and", "on", "is", "with", "your", "you", "this", "that"}


def _extract_keywords(text: str, max_keywords: int = 3) -> list[str]:
    words = [w.strip(".,!?").lower() for w in text.split()]
    keywords = [w for w in words if w and w not in _STOPWORDS]
    return keywords[:max_keywords] or [text[:20]]


def _default_storyboard(script_json: dict) -> list[dict]:
    """Built when the model omits storyboard or returns a malformed one,
    so the feature degrades to "generic per-beat shot" instead of losing
    the whole script generation over a formatting slip."""
    return [
        {
            "beat": beat,
            "visual": f"Visual for the {beat} beat: {script_json.get(beat, '')[:80]}",
            "keywords": _extract_keywords(str(script_json.get(beat, beat))),
        }
        for beat in STORYBOARD_BEATS
    ]


def _validate_storyboard(storyboard: object, script_json: dict) -> list[dict]:
    if not isinstance(storyboard, list) or len(storyboard) != len(STORYBOARD_BEATS):
        logger.warning("Storyboard missing or wrong length in model response, using a default one")
        return _default_storyboard(script_json)

    normalized = []
    for expected_beat, shot in zip(STORYBOARD_BEATS, storyboard):
        if not isinstance(shot, dict) or not shot.get("visual"):
            logger.warning("Storyboard shot for beat=%s malformed, using a default one", expected_beat)
            normalized.append(_default_storyboard(script_json)[STORYBOARD_BEATS.index(expected_beat)])
            continue
        keywords = shot.get("keywords")
        normalized.append(
            {
                "beat": expected_beat,
                "visual": str(shot["visual"]),
                "keywords": [str(k) for k in keywords] if isinstance(keywords, list) and keywords else _extract_keywords(str(shot["visual"])),
            }
        )
    return normalized


def _call_claude(system_prompt: str, user_prompt: str) -> dict:
    import anthropic

    if not settings.anthropic_api_key:
        raise RuntimeError("ANTHROPIC_API_KEY is not set")

    client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
    message = client.messages.create(
        model=settings.script_model,
        max_tokens=1536,
        system=system_prompt,
        messages=[{"role": "user", "content": user_prompt}],
    )
    raw_text = "".join(block.text for block in message.content if block.type == "text")

    try:
        script_json = json.loads(raw_text)
    except json.JSONDecodeError:
        logger.error("Claude response was not valid JSON: %s", raw_text)
        raise ValueError("Script generation returned malformed JSON from the model")

    script_json["storyboard"] = _validate_storyboard(script_json.get("storyboard"), script_json)
    return script_json


def has_existing_script(db: Session, topic: str) -> bool:
    """Per-topic script history check, so the same topic doesn't get a
    duplicate script generated for it."""
    return db.query(Script).filter(Script.topic == topic, Script.status != "rejected").first() is not None


def generate_script(
    db: Session,
    topic: str,
    style: str = DEFAULT_STYLE,
    length_variant: str = DEFAULT_LENGTH,
    trend_id: int | None = None,
    allow_duplicate: bool = False,
) -> Script:
    if not allow_duplicate and has_existing_script(db, topic):
        raise ValueError(f"A script already exists for topic '{topic}'. Pass allow_duplicate=True to override.")

    user_prompt = _build_user_prompt(topic, style, length_variant)
    script_json = _call_claude(SYSTEM_PROMPT, user_prompt)

    script = Script(
        trend_id=trend_id,
        topic=topic,
        script=script_json,
        style=style,
        length_variant=length_variant,
        status="draft",
    )
    db.add(script)

    if trend_id is not None:
        trend = db.get(Trend, trend_id)
        if trend:
            trend.used = True

    db.commit()
    db.refresh(script)
    return script


def regenerate_with_feedback(db: Session, script_id: int, feedback_note: str) -> Script:
    """Sends the edit note back to Claude for a rewrite, keeping the
    original script row in history and creating a new one linked to it
    via parent_script_id."""
    original = db.get(Script, script_id)
    if original is None:
        raise ValueError(f"Script {script_id} not found")

    user_prompt = _build_user_prompt(original.topic, original.style, original.length_variant, feedback_note)
    script_json = _call_claude(SYSTEM_PROMPT, user_prompt)

    new_script = Script(
        trend_id=original.trend_id,
        topic=original.topic,
        script=script_json,
        style=original.style,
        length_variant=original.length_variant,
        status="draft",
        feedback_note=feedback_note,
        parent_script_id=original.id,
    )
    original.status = "superseded"

    db.add(new_script)
    db.commit()
    db.refresh(new_script)
    return new_script
