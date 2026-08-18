"""Kokoro (self-hosted, Apache 2.0) TTS integration — the default voice
engine for Module 3.

Install: pip install kokoro soundfile  (see https://github.com/hexgrad/kokoro
for the current package name / model download instructions — the API below
targets the `KPipeline` interface as of kokoro>=0.3).

Word-level timestamps: Kokoro does not emit reliable word timing itself,
so per the spec this is deferred to Whisper in Module 4 (captions.py runs
word-level alignment against the rendered audio). This module only writes
the audio file.
"""
import logging
import wave
from pathlib import Path

from app.modules.voice.voice_profiles import resolve_voice

logger = logging.getLogger(__name__)


class KokoroUnavailable(RuntimeError):
    """Raised when the kokoro package / model weights aren't installed."""


def synthesize(text: str, out_path: str, voice_id: str | None = None, speed: float = 1.0) -> str:
    """Synthesizes `text` to a wav file at `out_path` using Kokoro.

    Raises KokoroUnavailable if the kokoro package isn't installed, so
    callers (see run.py) can fall back to the paid API.
    """
    voice = resolve_voice(voice_id)
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)

    try:
        import soundfile as sf
        from kokoro import KPipeline
    except ImportError as exc:
        raise KokoroUnavailable(
            "kokoro/soundfile not installed. Run: pip install kokoro soundfile"
        ) from exc

    pipeline = KPipeline(lang_code=voice[0])  # 'a' for american english, 'b' for british, etc.
    audio_chunks = []
    for _, _, audio in pipeline(text, voice=voice, speed=speed):
        audio_chunks.append(audio)

    if not audio_chunks:
        raise RuntimeError("Kokoro produced no audio output")

    import numpy as np

    full_audio = np.concatenate(audio_chunks)
    sf.write(out_path, full_audio, 24000)
    logger.info("Kokoro synthesized %s (%d chars) -> %s", voice, len(text), out_path)
    return out_path


def synthesize_silent_placeholder(text: str, out_path: str, seconds: float = 3.0) -> str:
    """Writes a silent PCM wav file so the rest of the pipeline (captions,
    ffmpeg assembly) can be exercised end-to-end without Kokoro's model
    weights installed. Not for production use — see synthesize() above.
    """
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    sample_rate = 24000
    n_frames = int(sample_rate * seconds)

    with wave.open(out_path, "w") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(b"\x00\x00" * n_frames)

    logger.warning("Kokoro unavailable — wrote a %.1fs silent placeholder to %s", seconds, out_path)
    return out_path
