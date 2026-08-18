"""Deduplicate near-identical topics before ranking / persisting."""
import re

from rapidfuzz import fuzz

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

    kept: list[dict] = []
    kept_normalized: list[str] = []

    for candidate in candidates:
        norm = candidate["normalized_topic"]

        if any(fuzz.token_sort_ratio(norm, existing) >= SIMILARITY_THRESHOLD for existing in existing_normalized):
            continue
        if any(fuzz.token_sort_ratio(norm, k) >= SIMILARITY_THRESHOLD for k in kept_normalized):
            continue

        kept.append(candidate)
        kept_normalized.append(norm)

    return kept
