"""Deduplicate near-identical topics before ranking / persisting."""
import re

from rapidfuzz import fuzz, process

SIMILARITY_THRESHOLD = 85  # 0-100, rapidfuzz token_sort_ratio


def normalize_topic(topic: str) -> str:
    text = topic.lower().strip()
    text = re.sub(r"[^\w\s]", "", text)
    text = re.sub(r"\s+", " ", text)
    return text


def dedupe_topics(candidates: list[dict], existing_normalized: set[str] | None = None) -> list[dict]:
    """Removes near-duplicate topics within `candidates`, and drops any
    topic that fuzzy-matches something already in `existing_normalized`
    (the topic-history set pulled from the DB), so the same topic is never
    suggested twice.

    Highest-scoring duplicate within a batch wins.
    """
    existing_normalized = existing_normalized or set()

    for c in candidates:
        c["normalized_topic"] = normalize_topic(c["topic"])

    # Highest score first so the best-scored variant of a duplicate cluster survives.
    candidates = sorted(candidates, key=lambda c: c["score"], reverse=True)

    # The history set only ever grows (topics are never pruned), while a
    # single run's candidates stay small and bounded — so the history
    # check is what actually needs to scale. A per-candidate Python loop
    # calling token_sort_ratio against every history entry is O(candidates
    # x history) and was measured at ~1.9s against 30k history rows;
    # rapidfuzz's cdist runs the same comparison as one vectorized batch
    # call and was ~16x faster at that scale (grows only with history
    # size, not with candidates x history).
    matches_history = [False] * len(candidates)
    if existing_normalized and candidates:
        existing_list = list(existing_normalized)
        norms = [c["normalized_topic"] for c in candidates]
        matrix = process.cdist(
            norms, existing_list, scorer=fuzz.token_sort_ratio, score_cutoff=SIMILARITY_THRESHOLD
        )
        matches_history = (matrix >= SIMILARITY_THRESHOLD).any(axis=1)

    # Within-batch dedup stays a plain nested loop: candidates per run are
    # few enough (tens, not thousands) that this is cheap, and it's
    # inherently sequential — whether a candidate is kept depends on which
    # higher-scored candidates were already accepted earlier in this loop.
    kept: list[dict] = []
    kept_normalized: list[str] = []

    for candidate, already_in_history in zip(candidates, matches_history):
        if already_in_history:
            continue

        norm = candidate["normalized_topic"]
        if any(fuzz.token_sort_ratio(norm, k) >= SIMILARITY_THRESHOLD for k in kept_normalized):
            continue

        kept.append(candidate)
        kept_normalized.append(norm)

    return kept
