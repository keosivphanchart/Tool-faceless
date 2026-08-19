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


def _parse_json_response(raw_text: str, source: str) -> dict:
    try:
        return json.loads(raw_text)
    except json.JSONDecodeError:
        logger.error("%s response was not valid JSON: %s", source, raw_text)
        raise ValueError(f"Script generation returned malformed JSON from {source}")


def _call_anthropic(system_prompt: str, user_prompt: str) -> dict:
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
    usage = getattr(message, "usage", None)
    if usage is not None:
        from faceless_pipeline.modules.automation.cost import record_cost

        record_cost("anthropic", settings.script_model, usage.input_tokens, usage.output_tokens)

    raw_text = "".join(block.text for block in message.content if block.type == "text")
    return _parse_json_response(raw_text, "Claude")


def _call_ollama(system_prompt: str, user_prompt: str) -> dict:
    """Free, local, no API key: talks to a locally-running Ollama server
    (https://ollama.com — `ollama pull <model>` once, then `ollama serve`
    keeps it running). Uses Ollama's /api/chat endpoint with format="json"
    to force valid JSON output from the model, same as we require from
    Claude. This is the alternative to a hosted API key — a one-time local
    model download instead of a recurring per-call cost.
    """
    import requests

    try:
        response = requests.post(
            f"{settings.ollama_base_url}/api/chat",
            json={
                "model": settings.ollama_model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                "format": "json",
                "stream": False,
            },
            timeout=180,  # local generation on CPU can be slow, especially for larger models
        )
        response.raise_for_status()
    except requests.exceptions.ConnectionError as exc:
        raise RuntimeError(
            f"Could not reach Ollama at {settings.ollama_base_url} — is `ollama serve` running? "
            f"Install from https://ollama.com, then `ollama pull {settings.ollama_model}`."
        ) from exc

    raw_text = response.json()["message"]["content"]
    return _parse_json_response(raw_text, "Ollama")


def _call_openai_compatible(
    base_url: str, api_key: str, model: str, system_prompt: str, user_prompt: str, provider_name: str
) -> dict:
    """Shared by OpenAI and Groq — Groq's hosted API deliberately mirrors
    OpenAI's /chat/completions request/response shape, so one HTTP call
    covers both, just pointed at a different base_url with a different key.
    """
    import requests

    if not api_key:
        raise RuntimeError(f"{provider_name} API key is not set")

    try:
        response = requests.post(
            f"{base_url}/chat/completions",
            headers={"Authorization": f"Bearer {api_key}"},
            json={
                "model": model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                "response_format": {"type": "json_object"},
            },
            timeout=60,
        )
        response.raise_for_status()
    except requests.exceptions.ConnectionError as exc:
        raise RuntimeError(f"Could not reach {provider_name} at {base_url}") from exc
    except requests.exceptions.HTTPError as exc:
        raise RuntimeError(f"{provider_name} API error ({response.status_code}): {response.text[:300]}") from exc

    payload = response.json()
    usage = payload.get("usage") or {}
    from faceless_pipeline.modules.automation.cost import record_cost

    record_cost(
        provider_name.lower(), model, usage.get("prompt_tokens", 0), usage.get("completion_tokens", 0)
    )

    raw_text = payload["choices"][0]["message"]["content"]
    return _parse_json_response(raw_text, provider_name)


def _call_openai(system_prompt: str, user_prompt: str) -> dict:
    return _call_openai_compatible(
        settings.openai_base_url, settings.openai_api_key, settings.openai_model, system_prompt, user_prompt, "OpenAI"
    )


def _call_groq(system_prompt: str, user_prompt: str) -> dict:
    return _call_openai_compatible(
        settings.groq_base_url, settings.groq_api_key, settings.groq_model, system_prompt, user_prompt, "Groq"
    )


def _call_gemini(system_prompt: str, user_prompt: str) -> dict:
    import requests

    if not settings.gemini_api_key:
        raise RuntimeError("GEMINI_API_KEY is not set")

    url = f"{settings.gemini_base_url}/models/{settings.gemini_model}:generateContent"
    try:
        response = requests.post(
            url,
            params={"key": settings.gemini_api_key},
            json={
                "systemInstruction": {"parts": [{"text": system_prompt}]},
                "contents": [{"role": "user", "parts": [{"text": user_prompt}]}],
                "generationConfig": {"responseMimeType": "application/json"},
            },
            timeout=60,
        )
        response.raise_for_status()
    except requests.exceptions.ConnectionError as exc:
        raise RuntimeError(f"Could not reach Gemini at {settings.gemini_base_url}") from exc
    except requests.exceptions.HTTPError as exc:
        raise RuntimeError(f"Gemini API error ({response.status_code}): {response.text[:300]}") from exc

    payload = response.json()
    usage = payload.get("usageMetadata") or {}
    from faceless_pipeline.modules.automation.cost import record_cost

    record_cost(
        "gemini", settings.gemini_model, usage.get("promptTokenCount", 0), usage.get("candidatesTokenCount", 0)
    )

    raw_text = payload["candidates"][0]["content"]["parts"][0]["text"]
    return _parse_json_response(raw_text, "Gemini")


_PROVIDERS = {
    "anthropic": _call_anthropic,
    "ollama": _call_ollama,
    "openai": _call_openai,
    "gemini": _call_gemini,
    "groq": _call_groq,
}


def _call_llm(system_prompt: str, user_prompt: str) -> dict:
    call = _PROVIDERS.get(settings.script_provider)
    if call is None:
        raise RuntimeError(f"Unknown SCRIPT_PROVIDER '{settings.script_provider}' — use one of {sorted(_PROVIDERS)}")

    from faceless_pipeline.modules.automation.cost import check_budget

    check_budget()  # raises BudgetExceeded if DAILY/MONTHLY_COST_BUDGET_USD is already hit; no-op if both are 0 (default)

    script_json = call(system_prompt, user_prompt)
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
    script_json = _call_llm(SYSTEM_PROMPT, user_prompt)

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
    script_json = _call_llm(SYSTEM_PROMPT, user_prompt)

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
