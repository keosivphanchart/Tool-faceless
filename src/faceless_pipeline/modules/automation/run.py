"""Automation: closes the loop from "trends exist" to "a video is
waiting in the review queue" without a human picking a topic, and closes
Module 8's feedback loop back into Module 2's style choice. All of this
is opt-in (see config.py's "Automation" settings, all default False) —
the pipeline's one mandatory human checkpoint (Module 5) is unaffected
either way; automation only decides *what* to generate, never skips
review.
"""
import logging
import random

from sqlalchemy.orm import Session

from faceless_pipeline.config import settings
from faceless_pipeline.models import Script, Trend
from faceless_pipeline.modules.scripts.generator import generate_script, has_existing_script
from faceless_pipeline.modules.scripts.presets import DEFAULT_STYLE, STYLE_PRESETS

logger = logging.getLogger(__name__)

# Exploration rate for choose_style()'s epsilon-greedy bandit: this
# fraction of picks ignore the historical best-performer and try a
# random style instead, so an early winner (possibly from a small
# sample) can't permanently starve every other style of new data.
AB_TEST_EXPLORATION_RATE = 0.2


def choose_style(db: Session) -> str:
    """Picks a script style, biased toward whichever has historically
    performed best (Module 8's `best_performing_patterns`), when
    AB_TEST_ENABLED. This is the "feed top patterns back into the script
    generator" step the README flagged as not wired up yet —
    `best_performing_patterns()` already returns exactly the ranking
    needed, this just acts on it for style selection.

    Epsilon-greedy: most picks exploit the current best style, but a
    fraction (AB_TEST_EXPLORATION_RATE) explore a random configured
    style instead, so the feedback loop keeps collecting data on
    non-winning styles rather than calcifying on whichever style
    happened to win first (possibly from very few data points).
    """
    styles = settings.ab_test_style_list or [DEFAULT_STYLE]

    if not settings.ab_test_enabled:
        return settings.auto_generate_style if settings.auto_generate_style in STYLE_PRESETS else DEFAULT_STYLE

    if random.random() < AB_TEST_EXPLORATION_RATE:
        return random.choice(styles)

    from faceless_pipeline.modules.analytics.run import best_performing_patterns

    ranked = best_performing_patterns(db)["by_style"]
    for row in ranked:
        if row["style"] in styles:
            return row["style"]

    # No performance data yet (nothing published/pulled) - round-robin
    # by how many scripts already exist, so early runs still spread
    # across styles instead of always picking the first one.
    return styles[db.query(Script).count() % len(styles)]


def auto_generate_from_trends(
    db: Session,
    count: int | None = None,
    min_score: float | None = None,
    length_variant: str | None = None,
) -> list[Script]:
    """Generates (and assembles into a video) a script for each of the
    top `count` unused trends scoring >= `min_score`, fully automating
    trend -> script -> video -> pending review with no human topic pick.
    A trend that already has a script (has_existing_script) or that
    fails generation is skipped, not fatal to the rest of the batch.
    """
    from faceless_pipeline.modules.video.run import assemble_pipeline

    count = count if count is not None else settings.auto_generate_count
    min_score = min_score if min_score is not None else settings.auto_generate_min_score
    length_variant = length_variant or settings.auto_generate_length_variant

    candidates = (
        db.query(Trend)
        .filter(Trend.used == False, Trend.score >= min_score)  # noqa: E712
        .order_by(Trend.score.desc())
        .limit(count)
        .all()
    )

    generated: list[Script] = []
    for trend in candidates:
        if has_existing_script(db, trend.topic):
            trend.used = True  # already covered elsewhere - don't keep re-selecting it every run
            db.commit()
            continue
        try:
            style = choose_style(db)
            script = generate_script(
                db, topic=trend.topic, style=style, length_variant=length_variant, trend_id=trend.id
            )
            assemble_pipeline(db, script.id)
            generated.append(script)
        except Exception:
            logger.exception("Auto-generate failed for trend %s ('%s')", trend.id, trend.topic)
            continue

    return generated
