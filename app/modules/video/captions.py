"""Word-level captions from the voice track.

Primary path: faster-whisper (pip install faster-whisper) transcribes the
rendered voiceover and returns word-level timestamps directly, which also
covers the "generate word-level timestamps" TODO deferred from Module 3.

Fallback path (no faster-whisper installed): evenly distribute the known
script text across the audio's duration. Timing will be less accurate but
the downstream ffmpeg caption-burn step still works.
"""
import json
import logging
import wave
from pathlib import Path

logger = logging.getLogger(__name__)


def _audio_duration_seconds(audio_path: str) -> float:
    try:
        with wave.open(audio_path, "rb") as wav_file:
            return wav_file.getnframes() / float(wav_file.getframerate())
    except Exception:
        logger.warning("Could not read wav duration for %s, defaulting to 30s", audio_path)
        return 30.0


def transcribe_words(audio_path: str) -> list[dict]:
    """Returns [{"word": str, "start": float, "end": float}, ...]."""
    try:
        from faster_whisper import WhisperModel
    except ImportError:
        raise RuntimeError("faster-whisper not installed; caller should use fallback_word_timing")

    model = WhisperModel("base.en", device="cpu", compute_type="int8")
    segments, _ = model.transcribe(audio_path, word_timestamps=True)

    words = []
    for segment in segments:
        for w in segment.words or []:
            words.append({"word": w.word.strip(), "start": w.start, "end": w.end})
    return words


def fallback_word_timing(script_text: str, audio_path: str) -> list[dict]:
    words = script_text.split()
    duration = _audio_duration_seconds(audio_path)
    if not words:
        return []
    per_word = duration / len(words)
    return [
        {"word": w, "start": i * per_word, "end": (i + 1) * per_word}
        for i, w in enumerate(words)
    ]


def words_to_srt(words: list[dict], out_path: str, words_per_caption: int = 4) -> str:
    """Groups words into short caption chunks (good for burned-in
    short-form captions) and writes an SRT file."""

    def fmt_ts(seconds: float) -> str:
        millis = int(round(seconds * 1000))
        h, remainder = divmod(millis, 3600_000)
        m, remainder = divmod(remainder, 60_000)
        s, ms = divmod(remainder, 1000)
        return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"

    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    lines = []
    for i in range(0, len(words), words_per_caption):
        chunk = words[i : i + words_per_caption]
        if not chunk:
            continue
        index = i // words_per_caption + 1
        start, end = chunk[0]["start"], chunk[-1]["end"]
        text = " ".join(w["word"] for w in chunk)
        lines.append(f"{index}\n{fmt_ts(start)} --> {fmt_ts(end)}\n{text}\n")

    Path(out_path).write_text("\n".join(lines), encoding="utf-8")
    return out_path


def generate_captions(audio_path: str, script_text: str, out_srt_path: str) -> str:
    try:
        words = transcribe_words(audio_path)
    except RuntimeError:
        logger.warning("Falling back to even-split caption timing (install faster-whisper for accurate timing)")
        words = fallback_word_timing(script_text, audio_path)

    words_json_path = str(Path(out_srt_path).with_suffix(".words.json"))
    Path(words_json_path).write_text(json.dumps(words, indent=2), encoding="utf-8")

    return words_to_srt(words, out_srt_path)
