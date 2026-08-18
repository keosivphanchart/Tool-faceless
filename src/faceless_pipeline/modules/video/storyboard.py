"""Turns a script's storyboard (one shot per beat: hook/promise/body/
payoff/cta) into an actual multi-segment background video, instead of
one static background for the whole runtime.

Each beat gets its own segment, sized to how long that beat actually
takes to narrate (from the word-level caption timestamps, since the
beats are concatenated into the narration in a known, fixed order) and
built from either real stock footage matching that beat's keywords, or —
with no stock footage key configured — a procedural gradient described
by that beat's own visual text, so different beats still look visually
distinct even with zero API keys.
"""
import logging
from pathlib import Path

from faceless_pipeline.config import settings
from faceless_pipeline.modules.scripts.generator import STORYBOARD_BEATS
from faceless_pipeline.modules.video.assemble import build_background, run_ffmpeg
from faceless_pipeline.modules.video.procedural_background import generate_procedural_background
from faceless_pipeline.modules.video.stock_footage import fetch_background_clips

logger = logging.getLogger(__name__)

# Only a safety floor against a literal zero/negative-duration ffmpeg
# call (e.g. a rounding hiccup in word timestamps) — NOT a target
# per-segment length. Each beat's duration below is already a real,
# contiguous slice of the total narration time (compute_beat_timing()
# slices one shared timeline), so segments naturally sum to the real
# audio duration. A per-segment floor any larger than this epsilon would
# inflate that sum past the real audio length — and since
# assemble_video() runs with -shortest, the *later* beats' segments
# would then get silently cut from the visible output while their
# captions (timed independently, off the real audio) kept playing over
# whatever segment was still on screen — a visual/caption mismatch this
# feature exists to prevent, not reintroduce.
MIN_SEGMENT_SECONDS = 0.15


def compute_beat_timing(script_json: dict, words: list[dict]) -> list[dict]:
    """Maps each storyboard beat to a (start, end) slice of the real
    narration audio, by giving each beat the same proportion of the total
    duration that its word count is of the total written word count.

    This is proportional, not a literal per-word index slice, because
    `words` isn't guaranteed to have the same count as the written
    script: the primary path transcribes the *rendered audio* with
    faster-whisper, and real ASR output routinely has a different word
    count than a plain .split() of the source text (numbers/abbreviations
    spoken and heard differently, filler words, merged/dropped tokens).
    An index-based slice silently ran out of words on drift like that and
    dropped the trailing beats from the storyboard entirely - meaning
    their background segments never got built, so the concatenated
    background ended before the narration did and ffmpeg's -shortest in
    assemble_video() truncated the real audio. Allocating by proportion
    of the known total duration instead always covers every beat and
    always sums to exactly the real audio span, regardless of transcript
    word-count drift.
    Returns [{"beat": ..., "start": float, "end": float}, ...].
    """
    if not words:
        return []

    total_start = words[0]["start"]
    total_duration = words[-1]["end"] - total_start
    if total_duration <= 0:
        return []

    beat_word_counts = [(beat, len(str(script_json.get(beat, "")).split())) for beat in STORYBOARD_BEATS]
    total_words = sum(count for _, count in beat_word_counts)
    if total_words == 0:
        return []

    timing = []
    words_so_far = 0
    for beat, word_count in beat_word_counts:
        if word_count == 0:
            continue
        start = total_start + (words_so_far / total_words) * total_duration
        words_so_far += word_count
        end = total_start + (words_so_far / total_words) * total_duration
        timing.append({"beat": beat, "start": start, "end": end})

    return timing


def build_storyboard_background(
    storyboard: list[dict], beat_timing: list[dict], out_dir: str, out_path: str
) -> str:
    """Builds one background video covering the full narration, cut into
    a segment per beat. Falls back to a single procedural background
    covering the whole video if there's no usable timing (e.g. captions
    failed) or fewer than 2 real segments — cutting between beats isn't
    worth it for a handful of words either.
    """
    Path(out_dir).mkdir(parents=True, exist_ok=True)
    storyboard_by_beat = {shot["beat"]: shot for shot in storyboard}

    segment_paths = []
    for i, beat_time in enumerate(beat_timing):
        duration = max(beat_time["end"] - beat_time["start"], MIN_SEGMENT_SECONDS)
        shot = storyboard_by_beat.get(beat_time["beat"], {})
        keywords = shot.get("keywords") or [beat_time["beat"]]
        segment_path = str(Path(out_dir) / f"segment_{i}_{beat_time['beat']}.mp4")

        clip_paths = fetch_background_clips(keywords, str(Path(out_dir) / f"clips_{beat_time['beat']}"))
        if clip_paths:
            build_background(clip_paths, duration, segment_path)
        else:
            generate_procedural_background(duration, segment_path, topic=shot.get("visual", beat_time["beat"]))

        segment_paths.append(segment_path)

    if len(segment_paths) < 2:
        logger.info("Fewer than 2 storyboard segments available, falling back to a single background")
        total_duration = beat_timing[-1]["end"] if beat_timing else MIN_SEGMENT_SECONDS
        generate_procedural_background(total_duration, out_path, topic="fallback")
        return out_path

    concat_list_path = str(Path(out_path).with_suffix(".concat.txt"))
    lines = [f"file '{Path(p).resolve()}'" for p in segment_paths]
    Path(concat_list_path).write_text("\n".join(lines), encoding="utf-8")

    cmd = [
        settings.ffmpeg_binary, "-y",
        "-f", "concat", "-safe", "0", "-i", concat_list_path,
        "-c:v", "libx264", "-pix_fmt", "yuv420p",
        out_path,
    ]
    run_ffmpeg(cmd)
    return out_path
