"""Module 3 orchestrator: script -> normalized voiceover audio file.

Usage:
    python -m faceless_pipeline.modules.voice.run <script_id> [--voice af_heart] [--dry-run]
"""
import argparse
import logging
from pathlib import Path

from sqlalchemy.orm import Session

from faceless_pipeline.db import SessionLocal, init_db
from faceless_pipeline.models import Script
from faceless_pipeline.modules.voice.fallback_tts import synthesize_fallback
from faceless_pipeline.modules.voice.kokoro_tts import KokoroUnavailable, synthesize, synthesize_silent_placeholder
from faceless_pipeline.modules.voice.normalize import normalize_loudness

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def script_to_narration_text(script_json: dict) -> str:
    parts = [script_json.get(k, "") for k in ("hook", "promise", "body", "payoff", "cta")]
    return " ".join(p.strip() for p in parts if p and p.strip())


def generate_voiceover(
    db: Session,
    script_id: int,
    voice_id: str | None = None,
    dry_run: bool = False,
    out_path: str | None = None,
) -> str:
    """Takes the caller's `db` session rather than opening its own —
    callers invoked from within an already-open request/session (e.g.
    Module 5's regenerate endpoints calling into Module 4's assemble
    pipeline) must not have this module silently open a second, competing
    session against the same connection.

    `out_path`, if given, overrides the default `./data/audio/{script_id}.wav`
    naming. Callers that assemble multiple videos from the same script
    (e.g. Module 5's "regenerate video") must pass a distinct out_path per
    attempt — otherwise every attempt writes over the same file, and any
    earlier video's `audio_path` silently starts pointing at newer audio.
    """
    script = db.get(Script, script_id)
    if script is None:
        raise ValueError(f"Script {script_id} not found")

    text = script_to_narration_text(script.script)
    final_path = out_path or f"./data/audio/{script_id}.wav"
    raw_path = str(Path(final_path).with_name(Path(final_path).stem + "_raw" + Path(final_path).suffix))
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


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("script_id", type=int)
    parser.add_argument("--voice", default=None)
    parser.add_argument("--dry-run", action="store_true", help="Skip real TTS, write silent audio")
    args = parser.parse_args()

    init_db()
    cli_db = SessionLocal()
    try:
        path = generate_voiceover(cli_db, args.script_id, voice_id=args.voice, dry_run=args.dry_run)
        print(f"Voiceover written to {path}")
    finally:
        cli_db.close()
