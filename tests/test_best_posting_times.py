"""best_posting_times(): suggests, per platform, which hour of day
(UTC) has historically drawn the most average views - same
latest-per-(video,platform) dedup as best_performing_patterns(), but
grouped by Video.published_at.hour instead of script style/topic.
"""
from datetime import datetime, timedelta

from faceless_pipeline.models import Performance, Script, Video, VideoStatus
from faceless_pipeline.modules.analytics.run import best_posting_times


def _make_published_video(db_session, topic: str, published_at: datetime) -> Video:
    script = Script(topic=topic, script={}, style="explainer", length_variant="30s", status="draft")
    db_session.add(script)
    db_session.commit()
    db_session.refresh(script)

    video = Video(script_id=script.id, status=VideoStatus.published, published_at=published_at)
    db_session.add(video)
    db_session.commit()
    db_session.refresh(video)
    return video


def test_no_data_returns_empty_dict(db_session):
    assert best_posting_times(db_session) == {}


def test_ranks_hours_by_average_views_per_platform(db_session):
    morning = _make_published_video(db_session, "Morning post", datetime(2024, 1, 1, 9, 0))
    evening = _make_published_video(db_session, "Evening post", datetime(2024, 1, 1, 18, 0))
    db_session.add(Performance(video_id=morning.id, platform="youtube", views=100, pulled_at=datetime.utcnow()))
    db_session.add(Performance(video_id=evening.id, platform="youtube", views=900, pulled_at=datetime.utcnow()))
    db_session.commit()

    result = best_posting_times(db_session)

    assert result["youtube"][0] == {"hour": 18, "avg_views": 900.0, "sample_count": 1}
    assert result["youtube"][1] == {"hour": 9, "avg_views": 100.0, "sample_count": 1}


def test_averages_multiple_posts_in_the_same_hour(db_session):
    a = _make_published_video(db_session, "A", datetime(2024, 1, 1, 18, 0))
    b = _make_published_video(db_session, "B", datetime(2024, 1, 3, 18, 30))
    db_session.add(Performance(video_id=a.id, platform="tiktok", views=200, pulled_at=datetime.utcnow()))
    db_session.add(Performance(video_id=b.id, platform="tiktok", views=600, pulled_at=datetime.utcnow()))
    db_session.commit()

    result = best_posting_times(db_session)

    assert result["tiktok"][0] == {"hour": 18, "avg_views": 400.0, "sample_count": 2}


def test_unpublished_timestamp_excluded_from_ranking(db_session):
    dated = _make_published_video(db_session, "Dated", datetime(2024, 1, 1, 12, 0))
    undated = Video(script_id=dated.script_id, status=VideoStatus.published, published_at=None)
    db_session.add(undated)
    db_session.commit()
    db_session.add(Performance(video_id=dated.id, platform="youtube", views=50, pulled_at=datetime.utcnow()))
    db_session.add(Performance(video_id=undated.id, platform="youtube", views=99999, pulled_at=datetime.utcnow()))
    db_session.commit()

    result = best_posting_times(db_session)

    assert len(result["youtube"]) == 1
    assert result["youtube"][0]["avg_views"] == 50.0


def test_only_latest_pull_per_video_platform_is_used(db_session):
    video = _make_published_video(db_session, "Repeat pulls", datetime(2024, 1, 1, 8, 0))
    db_session.add(
        Performance(video_id=video.id, platform="youtube", views=10, pulled_at=datetime.utcnow() - timedelta(weeks=2))
    )
    db_session.add(Performance(video_id=video.id, platform="youtube", views=5000, pulled_at=datetime.utcnow()))
    db_session.commit()

    result = best_posting_times(db_session)

    assert result["youtube"][0]["avg_views"] == 5000.0
