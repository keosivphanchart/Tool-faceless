"""Writes the metadata sidecar file (title, description, tags) that ships
alongside the final .mp4, ready for Module 6 to hand to the platform API.
"""
import json
from pathlib import Path


def write_metadata(script_json: dict, topic: str, out_path: str, tags: list[str] | None = None) -> str:
    title = script_json.get("hook", topic)[:100]
    description = "\n\n".join(
        part for part in (script_json.get("promise"), script_json.get("body"), script_json.get("cta")) if part
    )
    metadata = {
        "title": title,
        "description": description,
        "tags": tags or [],
        "topic": topic,
    }
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    Path(out_path).write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    return out_path
