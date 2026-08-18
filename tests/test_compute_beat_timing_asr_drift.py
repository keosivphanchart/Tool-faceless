"""Regression test: compute_beat_timing() must not silently drop trailing
storyboard beats when the real transcript has fewer words than the
written script implies.

Bug: the original implementation counted words per beat from the written
script text (beat_text.split()) and sliced that many words off the front
of the real `words` list to find each beat's (start, end). That only
lines up exactly when `words` was built the same way (the even-split
fallback, which literally splits the same text). faster-whisper's
word-level transcript is a real ASR output — a different word count than
a plain .split() of the source text is routine (numbers/abbreviations
spoken vs. transcribed differently, filler words, merged tokens) — so on
real (non-fallback) runs, the cursor could run past the end of `words`
before reaching the later beats, and `if not segment_words: break` then
silently dropped them from the returned timing.

That's not just an accuracy nit: video/run.py only builds a background
segment for beats present in compute_beat_timing()'s output, so a
dropped trailing beat meant the concatenated background ended before the
real narration did — and assemble_video()'s ffmpeg -shortest then
truncated the actual audio, cutting off spoken content, exactly the
class of bug already fixed once for MIN_SEGMENT_SECONDS but reintroduced
here through transcript word-count drift instead.

Fixed by allocating each beat a proportional share of the real audio's
total (start, end) span based on written word-count ratios, instead of
indexing into `words` by position — this always covers every non-empty
beat and always sums to exactly the real audio duration, regardless of
how many words the transcript actually contains.
"""
from faceless_pipeline.modules.video.storyboard import STORYBOARD_BEATS, compute_beat_timing


def _make_words(count: int, word_seconds: float = 0.3) -> list[dict]:
    words = []
    t = 0.0
    for i in range(count):
        words.append({"word": f"w{i}", "start": t, "end": t + word_seconds})
        t += word_seconds
    return words


def test_transcript_with_fewer_words_than_script_still_covers_every_beat():
    script_json = {
        "hook": "w " * 7,
        "promise": "w " * 6,
        "body": "w " * 9,
        "payoff": "w " * 6,
        "cta": "w " * 6,
    }  # 34 words as written

    # A real ASR transcript with noticeably fewer tokens than the written
    # script implies -- entirely plausible (numbers, filler words, fast
    # speech). The old index-slicing implementation dropped "payoff" and
    # "cta" entirely here.
    words = _make_words(20)

    timing = compute_beat_timing(script_json, words)

    covered_beats = [row["beat"] for row in timing]
    assert covered_beats == STORYBOARD_BEATS, "every non-empty beat must appear in the timing, none silently dropped"


def test_timing_always_spans_exactly_the_real_audio_duration():
    script_json = {
        "hook": "w " * 3,
        "promise": "w " * 40,  # heavily lopsided vs. the transcript below
        "body": "w " * 2,
        "payoff": "w " * 1,
        "cta": "w " * 5,
    }
    words = _make_words(9)  # far fewer than the 51 words the script implies

    timing = compute_beat_timing(script_json, words)

    assert timing[0]["start"] == words[0]["start"]
    assert timing[-1]["end"] == words[-1]["end"], "beat coverage must never fall short of the real narration audio"
    # Contiguous, non-overlapping, monotonically increasing.
    for prev, cur in zip(timing, timing[1:]):
        assert prev["end"] == cur["start"]


def test_matching_word_counts_still_produce_sane_even_split_timing():
    """The even-split fallback path (fallback_word_timing) always has
    words == script_text.split(), i.e. matching counts by construction —
    confirms the proportional rewrite still behaves sensibly there too."""
    script_json = {
        "hook": "a b",
        "promise": "c d e",
        "body": "f",
        "payoff": "g h",
        "cta": "i",
    }
    words = _make_words(9)

    timing = compute_beat_timing(script_json, words)

    assert [row["beat"] for row in timing] == STORYBOARD_BEATS
    assert timing[0]["start"] == 0.0
    assert timing[-1]["end"] == words[-1]["end"]
