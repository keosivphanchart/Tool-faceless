"""cleanup_stale_data(): purges old rejected videos (+ their files) and
old superseded scripts, but only past the retention window and never
anything still referenced.
"""
from datetime import datetime, timedelta

from faceless_pipeline.models import Script, Video, VideoStatus
from faceless_pipeline.modules.automation.cleanup import cleanup_stale_data


def _make_script(db_session, topic: str, status: str, created_at: datetime) -> Script:
    script = Script(topic=topic, script={"hook": "h"}, status=status, created_at=created_at)
    db_session.add(script)
    db_session.commit()
    db_session.refresh(script)
    return script


def _make_video(db_session, script_id: int, status, created_at: datetime, file_path: str | None = None) -> Video:
    video = Video(script_id=script_id, status=status, created_at=created_at, file_path=file_path)
    db_session.add(video)
    db_session.commit()
    db_session.refresh(video)
    return video


def test_deletes_old_rejected_videos(db_session):
    script = _make_script(db_session, "Old rejected", "draft", datetime.utcnow() - timedelta(days=60))
    old_video = _make_video(
        db_session, script.id, VideoStatus.rejected, datetime.utcnow() - timedelta(days=60)
    )

    result = cleanup_stale_data(db_session, retention_days=30)

    assert result["videos_deleted"] == 1
    assert db_session.get(Video, old_video.id) is None


def test_keeps_recent_rejected_videos(db_session):
    script = _make_script(db_session, "Recent rejected", "draft", datetime.utcnow())
    recent_video = _make_video(db_session, script.id, VideoStatus.rejected, datetime.utcnow())

    result = cleanup_stale_data(db_session, retention_days=30)

    assert result["videos_deleted"] == 0
    assert db_session.get(Video, recent_video.id) is not None


def test_keeps_pending_approved_and_published_videos_regardless_of_age(db_session):
    old = datetime.utcnow() - timedelta(days=90)
    for status in (VideoStatus.pending, VideoStatus.approved, VideoStatus.published):
        script = _make_script(db_session, f"Kept {status}", "draft", old)
        _make_video(db_session, script.id, status, old)

    result = cleanup_stale_data(db_session, retention_days=30)

    assert result["videos_deleted"] == 0
    assert db_session.query(Video).count() == 3


def test_deletes_the_rejected_videos_media_files_from_disk(db_session, tmp_path):
    video_file = tmp_path / "video.mp4"
    video_file.write_bytes(b"fake")
    thumb_file = tmp_path / "thumb.jpg"
    thumb_file.write_bytes(b"fake")

    script = _make_script(db_session, "Files cleanup", "draft", datetime.utcnow() - timedelta(days=60))
    video = _make_video(db_session, script.id, VideoStatus.rejected, datetime.utcnow() - timedelta(days=60))
    video.file_path = str(video_file)
    video.thumbnail_path = str(thumb_file)
    db_session.commit()

    cleanup_stale_data(db_session, retention_days=30)

    assert not video_file.exists()
    assert not thumb_file.exists()


def test_deletes_old_superseded_scripts_with_no_remaining_videos(db_session):
    script = _make_script(db_session, "Old superseded", "superseded", datetime.utcnow() - timedelta(days=60))

    result = cleanup_stale_data(db_session, retention_days=30)

    assert result["scripts_deleted"] == 1
    assert db_session.get(Script, script.id) is None


def test_keeps_old_superseded_script_if_a_video_still_references_it(db_session):
    """A superseded script must never be deleted while a Video row still
    points at it - Video.script_id is a NOT NULL foreign key and SQLite
    doesn't enforce FK constraints in this project, so that would leave
    a silently dangling reference instead of erroring."""
    old = datetime.utcnow() - timedelta(days=60)
    script = _make_script(db_session, "Superseded but referenced", "superseded", old)
    # Its video is still 'approved' (not rejected), e.g. an older attempt
    # that was itself approved before the script got superseded by a
    # later rewrite - contrived for the test, but the FK must hold either way.
    _make_video(db_session, script.id, VideoStatus.approved, old)

    result = cleanup_stale_data(db_session, retention_days=30)

    assert result["scripts_deleted"] == 0
    assert db_session.get(Script, script.id) is not None


def test_keeps_recent_superseded_scripts(db_session):
    script = _make_script(db_session, "Recent superseded", "superseded", datetime.utcnow())

    result = cleanup_stale_data(db_session, retention_days=30)

    assert result["scripts_deleted"] == 0
    assert db_session.get(Script, script.id) is not None
