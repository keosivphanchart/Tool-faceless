"""Writes the metadata sidecar file (title, description, tags) that ships
alongside the final .mp4, ready for Module 6 to hand to the platform API.
"""
import json
from pathlib import Path


def tags_from_storyboard(script_json: dict, max_tags: int = 15) -> list[str]:
    """Storyboard shots already carry 2-3 search keywords each, generated
    specifically to match footage per beat - the same terms double as
    good video tags/hashtags, so this reuses them instead of publishing
    with no tags at all (the only prior source of tags was an explicit
    caller-supplied list that nothing ever actually passed)."""
    storyboard = script_json.get("storyboard") or []
    tags: list[str] = []
    seen_lower: set[str] = set()
    for shot in storyboard:
        for keyword in shot.get("keywords") or []:
            keyword = str(keyword).strip()
            if keyword and keyword.lower() not in seen_lower:
                tags.append(keyword)
                seen_lower.add(keyword.lower())
    return tags[:max_tags]


def write_metadata(script_json: dict, topic: str, out_path: str, tags: list[str] | None = None) -> str:
    title = script_json.get("hook", topic)[:100]
    description = "\n\n".join(
        part for part in (script_json.get("promise"), script_json.get("body"), script_json.get("cta")) if part
    )
    metadata = {
        "title": title,
        "description": description,
        "tags": tags if tags is not None else tags_from_storyboard(script_json),
        "topic": topic,
    }
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    Path(out_path).write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    return out_path
