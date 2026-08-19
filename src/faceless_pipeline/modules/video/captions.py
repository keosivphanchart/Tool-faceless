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


def audio_duration_seconds(audio_path: str) -> float:
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
    duration = audio_duration_seconds(audio_path)
    if not words:
        return []
    per_word = duration / len(words)
    return [
        {"word": w, "start": i * per_word, "end": (i + 1) * per_word}
        for i, w in enumerate(words)
    ]


_ASS_HEADER_TEMPLATE = """[Script Info]
Title: Karaoke Captions
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920
WrapStyle: 0
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Karaoke,Arial Black,72,{highlight},{base},&H00000000,&H00000000,-1,0,0,0,100,100,0,0,3,3,0,2,60,60,160,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""


def words_to_ass(
    words: list[dict],
    out_path: str,
    words_per_caption: int = 4,
    highlight_color: str = "&H0000D7FF&",
    base_color: str = "&H00FFFFFF&",
) -> str:
    """Groups words into short caption chunks and writes an ASS file with
    per-word `\\kf` karaoke-fill tags plus a brief scale-up "pop" on each
    word as it becomes active — the CapCut/TikTok animated-caption look.
    Rendered natively by libass (the same engine ffmpeg's `subtitles`
    filter already uses for plain SRT), so no new dependency is needed.
    """

    def fmt_ts(seconds: float) -> str:
        centis = int(round(max(0.0, seconds) * 100))
        h, remainder = divmod(centis, 360000)
        m, remainder = divmod(remainder, 6000)
        s, cs = divmod(remainder, 100)
        return f"{h:d}:{m:02d}:{s:02d}.{cs:02d}"

    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    body_lines = []
    for i in range(0, len(words), words_per_caption):
        chunk = [w for w in words[i : i + words_per_caption] if w["word"].strip()]
        if not chunk:
            continue
        chunk_start = chunk[0]["start"]
        chunk_end = max(chunk[-1]["end"], chunk_start + 0.01)

        parts = []
        for j, w in enumerate(chunk):
            next_start = chunk[j + 1]["start"] if j + 1 < len(chunk) else chunk_end
            duration_cs = max(1, round((next_start - w["start"]) * 100))
            pop_start_ms = max(0, round((w["start"] - chunk_start) * 1000))
            text = w["word"].strip().replace("{", "").replace("}", "")
            parts.append(
                f"{{\\kf{duration_cs}\\t({pop_start_ms},{pop_start_ms + 80},\\fscx115\\fscy115)"
                f"\\t({pop_start_ms + 80},{pop_start_ms + 160},\\fscx100\\fscy100)}}{text}"
            )

        text_line = " ".join(parts)
        body_lines.append(f"Dialogue: 0,{fmt_ts(chunk_start)},{fmt_ts(chunk_end)},Karaoke,,0,0,0,,{text_line}")

    header = _ASS_HEADER_TEMPLATE.format(highlight=highlight_color, base=base_color)
    Path(out_path).write_text(header + "\n".join(body_lines) + "\n", encoding="utf-8")
    return out_path


def generate_captions(audio_path: str, script_text: str, out_ass_path: str) -> tuple[str, list[dict]]:
    """Returns (ass_path, words) — callers that only need the caption
    file can ignore the second value; video/storyboard.py uses the
    word-level timestamps to figure out which time range of the final
    video belongs to which script beat.
    """
    try:
        words = transcribe_words(audio_path)
    except RuntimeError:
        logger.warning("Falling back to even-split caption timing (install faster-whisper for accurate timing)")
        words = fallback_word_timing(script_text, audio_path)

    words_json_path = str(Path(out_ass_path).with_suffix(".words.json"))
    Path(words_json_path).write_text(json.dumps(words, indent=2), encoding="utf-8")

    return words_to_ass(words, out_ass_path), words
