"""build_digest_message(): a rollup of trends/scripts/videos over the
configured window, plus the current top performer if there's any
performance data at all.
"""
from datetime import datetime, timedelta

from faceless_pipeline.config import settings
from faceless_pipeline.models import Performance, Script, Trend, Video, VideoStatus
from faceless_pipeline.modules.automation.digest import build_digest_message


def test_counts_recent_trends_scripts_and_published_videos(db_session):
    original = settings.digest_interval_hours
    settings.digest_interval_hours = 24
    try:
        db_session.add(Trend(topic="T1", normalized_topic="t1", source="google_trends", score=1, created_at=datetime.utcnow()))
        db_session.add(Trend(topic="T2", normalized_topic="t2", source="google_trends", score=1, created_at=datetime.utcnow() - timedelta(days=5)))

        script = Script(topic="S1", script={}, status="draft", created_at=datetime.utcnow())
        db_session.add(script)
        db_session.commit()
        db_session.refresh(script)

        db_session.add(Video(script_id=script.id, status=VideoStatus.published, created_at=datetime.utcnow()))
        db_session.commit()

        message = build_digest_message(db_session)

        assert "1 new trend found" in message
        assert "1 script generated" in message
        assert "1 video published" in message
    finally:
        settings.digest_interval_hours = original


def test_includes_top_performer_when_data_exists(db_session):
    original = settings.digest_interval_hours
    settings.digest_interval_hours = 24
    try:
        script = Script(topic="Top topic", script={}, status="draft")
        db_session.add(script)
        db_session.commit()
        db_session.refresh(script)

        video = Video(script_id=script.id, status=VideoStatus.published)
        db_session.add(video)
        db_session.commit()
        db_session.refresh(video)

        db_session.add(Performance(video_id=video.id, platform="youtube", views=12345, pulled_at=datetime.utcnow()))
        db_session.commit()

        message = build_digest_message(db_session)

        assert "Top topic" in message
        assert "12345" in message
    finally:
        settings.digest_interval_hours = original


def test_no_performance_data_omits_top_performer_line(db_session):
    message = build_digest_message(db_session)

    assert "Top performer" not in message
