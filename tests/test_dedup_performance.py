"""dedupe_topics() used to compare each candidate against the entire
trend-history set with a Python-level loop calling fuzz.token_sort_ratio
one pair at a time - O(candidates x history). Since history only ever
grows (topics are never pruned) while a single run's candidate count
stays small, this got slower every single day the trend finder ran:
measured ~1.9s at 30k history rows.

It was rewritten to run the history check as one vectorized
rapidfuzz.process.cdist call instead (~16-20x faster at that scale). This
file locks in that the rewrite didn't change *behavior*, only speed, and
covers the edge cases (empty candidates/history) the vectorized path has
to special-case that the naive nested loop didn't.
"""
import random

from rapidfuzz import fuzz

from faceless_pipeline.modules.trends.dedup import SIMILARITY_THRESHOLD, dedupe_topics, normalize_topic


def _naive_dedupe(candidates, existing_normalized):
    """The original O(candidates x history) implementation, kept here
    only as an oracle to check the optimized version against."""
    for c in candidates:
        c["normalized_topic"] = normalize_topic(c["topic"])
    candidates = sorted(candidates, key=lambda c: c["score"], reverse=True)
    kept, kept_normalized = [], []
    for candidate in candidates:
        norm = candidate["normalized_topic"]
        if any(fuzz.token_sort_ratio(norm, e) >= SIMILARITY_THRESHOLD for e in existing_normalized):
            continue
        if any(fuzz.token_sort_ratio(norm, k) >= SIMILARITY_THRESHOLD for k in kept_normalized):
            continue
        kept.append(candidate)
        kept_normalized.append(norm)
    return kept


def test_cdist_rewrite_matches_naive_implementation_across_random_trials():
    rng = random.Random(7)
    words = ["ai", "tools", "productivity", "hacks", "finance", "budget", "apps", "2026", "best", "top"]

    def rand_topic():
        return " ".join(rng.choices(words, k=rng.randint(2, 5)))

    for trial in range(100):
        existing = {rand_topic() for _ in range(rng.randint(0, 50))}
        candidates_a = [
            {"topic": rand_topic(), "source": "x", "score": rng.random() * 100}
            for _ in range(rng.randint(0, 30))
        ]
        candidates_b = [dict(c) for c in candidates_a]

        result_new = dedupe_topics(candidates_a, existing_normalized=set(existing))
        result_old = _naive_dedupe(candidates_b, existing)

        topics_new = sorted(c["topic"] for c in result_new)
        topics_old = sorted(c["topic"] for c in result_old)
        assert topics_new == topics_old, f"trial {trial}: {topics_new} != {topics_old}"


def test_dedupe_topics_handles_empty_candidates():
    assert dedupe_topics([], existing_normalized={"a", "b"}) == []


def test_dedupe_topics_handles_empty_history():
    result = dedupe_topics([{"topic": "x y z", "source": "s", "score": 1}], existing_normalized=set())
    assert [c["topic"] for c in result] == ["x y z"]


def test_dedupe_topics_handles_both_empty():
    assert dedupe_topics([], existing_normalized=set()) == []
