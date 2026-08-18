from app.modules.trends.dedup import dedupe_topics, normalize_topic


def test_normalize_topic_strips_punctuation_and_case():
    assert normalize_topic("AI Productivity Tools!!") == "ai productivity tools"


def test_dedupe_collapses_near_duplicates_keeping_highest_score():
    candidates = [
        {"topic": "AI Productivity Tools", "source": "google_trends", "score": 40},
        {"topic": "ai productivity tools!", "source": "youtube", "score": 90},
        {"topic": "Home workout routines", "source": "reddit", "score": 30},
    ]
    result = dedupe_topics(candidates, existing_normalized=set())

    assert len(result) == 2
    topics = {(r["topic"], r["source"]) for r in result}
    assert ("ai productivity tools!", "youtube") in topics
    assert ("Home workout routines", "reddit") in topics


def test_dedupe_drops_topics_already_seen_in_history():
    candidates = [{"topic": "Best budgeting apps 2026", "source": "reddit", "score": 30}]
    result = dedupe_topics(candidates, existing_normalized={"best budgeting apps 2025"})
    assert result == []


def test_dedupe_keeps_genuinely_distinct_topics():
    candidates = [{"topic": "Best budgeting apps 2026", "source": "reddit", "score": 30}]
    result = dedupe_topics(candidates, existing_normalized={"how to train a puppy"})
    assert len(result) == 1
