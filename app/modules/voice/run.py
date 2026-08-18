"""Module 3 orchestrator: script -> normalized voiceover audio file.

Usage:
    python -m app.modules.voice.run <script_id> [--voice af_heart] [--dry-run]
"""
import argparse
import logging
from pathlib import Path

from app.db import SessionLocal, init_db
from app.models import Script
from app.modules.voice.fallback_tts import synthesize_fallback
from app.modules.voice.kokoro_tts import KokoroUnavailable, synthesize, synthesize_silent_placeholder
from app.modules.voice.normalize import normalize_loudness

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def script_to_narration_text(script_json: dict) -> str:
    parts = [script_json.get(k, "") for k in ("hook", "promise", "body", "payoff", "cta")]
    return " ".join(p.strip() for p in parts if p and p.strip())


def generate_voiceover(script_id: int, voice_id: str | None = None, dry_run: bool = False) -> str:
    db = SessionLocal()
    try:
        script = db.get(Script, script_id)
        if script is None:
            raise ValueError(f"Script {script_id} not found")

        text = script_to_narration_text(script.script)
        raw_path = f"./data/audio/{script_id}_raw.wav"
        final_path = f"./data/audio/{script_id}.wav"
        Path(raw_path).parent.mkdir(parents=True, exist_ok=True)

        if dry_run:
            synthesize_silent_placeholder(text, raw_path)
        else:
            try:
                synthesize(text, raw_path, voice_id=voice_id)
            except KokoroUnavailable:
                logger.warning("Kokoro unavailable, trying paid fallback API")
                try:
                    synthesize_fallback(text, raw_path)
                except Exception:
                    logger.warning("Fallback TTS also unavailable, writing silent placeholder")
                    synthesize_silent_placeholder(text, raw_path)

        try:
            normalize_loudness(raw_path, final_path)
        except Exception:
            logger.warning("Loudness normalization unavailable (ffmpeg missing?), using raw audio")
            final_path = raw_path

        return final_path
    finally:
        db.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("script_id", type=int)
    parser.add_argument("--voice", default=None)
    parser.add_argument("--dry-run", action="store_true", help="Skip real TTS, write silent audio")
    args = parser.parse_args()

    init_db()
    path = generate_voiceover(args.script_id, voice_id=args.voice, dry_run=args.dry_run)
    print(f"Voiceover written to {path}")
