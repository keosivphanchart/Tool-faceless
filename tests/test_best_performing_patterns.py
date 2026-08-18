"""Regression test: best_performing_patterns() must average one row per
(video, platform) - the most recent pull - not every historical row.

Bug: pull_all_performance() is a *weekly* job that inserts a new
Performance row per video per platform on every run instead of updating
one in place, so a long-lived video accumulates many rows over time. The
original best_performing_patterns() grouped and averaged across every
row ever pulled, so a video's own pull *count* skewed the style/topic
average it belongs to - a mediocre video tracked for 20 weeks could
outweigh 20 different one-pull videos in the same style bucket, which is
backwards for a "what's working" signal meant to guide future script
generation. Fixed to only consider each video's latest Performance row
per platform.
"""
from datetime import datetime, timedelta

from faceless_pipeline.models import Performance, Script, Video, VideoStatus
from faceless_pipeline.modules.analytics.run import best_performing_patterns


def _make_published_video(db_session, topic: str, style: str) -> Video:
    script = Script(topic=topic, script={}, style=style, length_variant="30s", status="draft")
    db_session.add(script)
    db_session.commit()
    db_session.refresh(script)

    video = Video(script_id=script.id, status=VideoStatus.published)
    db_session.add(video)
    db_session.commit()
    db_session.refresh(video)
    return video


def test_repeated_weekly_pulls_do_not_skew_the_average(db_session):
    video_a = _make_published_video(db_session, "Topic A", "explainer")
    video_b = _make_published_video(db_session, "Topic B", "explainer")

    # video_a: pulled once, low views.
    db_session.add(Performance(video_id=video_a.id, platform="youtube", views=100, retention_pct=50.0, pulled_at=datetime.utcnow()))
    # video_b: pulled 20 times (a long-lived video tracked weekly), views
    # consistently high but no better than a single fair sample would show.
    for i in range(20):
        db_session.add(
            Performance(
                video_id=video_b.id,
                platform="youtube",
                views=5000,
                retention_pct=80.0,
                pulled_at=datetime.utcnow() - timedelta(weeks=20 - i),
            )
        )
    db_session.commit()

    result = best_performing_patterns(db_session)

    assert len(result["by_style"]) == 1
    # Fair per-video average: (100 + 5000) / 2, not dominated by video_b's
    # 20 near-duplicate rows.
    assert result["by_style"][0]["views"] == (100 + 5000) / 2


def test_only_the_latest_pull_per_video_and_platform_is_used(db_session):
    video = _make_published_video(db_session, "Topic C", "listicle")

    old = datetime.utcnow() - timedelta(weeks=2)
    newer = datetime.utcnow() - timedelta(weeks=1)
    newest = datetime.utcnow()
    db_session.add(Performance(video_id=video.id, platform="youtube", views=100, retention_pct=10.0, pulled_at=old))
    db_session.add(Performance(video_id=video.id, platform="youtube", views=200, retention_pct=20.0, pulled_at=newer))
    db_session.add(Performance(video_id=video.id, platform="youtube", views=9000, retention_pct=90.0, pulled_at=newest))
    db_session.commit()

    result = best_performing_patterns(db_session)

    assert result["by_style"][0]["views"] == 9000
    assert result["by_style"][0]["retention_pct"] == 90.0


def test_different_platforms_for_the_same_video_are_each_kept_at_their_latest(db_session):
    video = _make_published_video(db_session, "Topic D", "story")

    db_session.add(Performance(video_id=video.id, platform="youtube", views=1000, retention_pct=40.0, pulled_at=datetime.utcnow() - timedelta(weeks=1)))
    db_session.add(Performance(video_id=video.id, platform="youtube", views=2000, retention_pct=50.0, pulled_at=datetime.utcnow()))
    db_session.add(Performance(video_id=video.id, platform="tiktok", views=500, retention_pct=60.0, pulled_at=datetime.utcnow()))
    db_session.commit()

    result = best_performing_patterns(db_session)

    # Latest youtube (2000) + latest tiktok (500) averaged, not the stale
    # youtube row (1000) alongside them.
    assert result["by_style"][0]["views"] == (2000 + 500) / 2
