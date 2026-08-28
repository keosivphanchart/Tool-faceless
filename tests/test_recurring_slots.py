"""Recurring posting slots: a PostingSlot fires once per day, at its
configured day/time, and publishes whichever approved video has been
waiting longest - the alternative to Video.scheduled_for's "pick one
datetime by hand" flow tested in test_scheduled_publish.py.
"""
from datetime import datetime, timedelta
from unittest.mock import patch

from fastapi.testclient import TestClient

from faceless_pipeline.main import app
from faceless_pipeline.models import PostingSlot, Script, Video, VideoStatus
from faceless_pipeline.modules.publisher.recurring import dispatch_due_posting_slots

client = TestClient(app)


def _make_approved_video(db_session, topic: str, tmp_path, created_at: datetime | None = None) -> Video:
    script = Script(topic=topic, script={"hook": "h", "promise": "p", "body": "b", "payoff": "pa", "cta": "c"})
    db_session.add(script)
    db_session.commit()
    db_session.refresh(script)

    fake_video_file = tmp_path / f"{topic.replace(' ', '_')}.mp4"
    fake_video_file.write_bytes(b"not a real mp4, just needs to exist")

    video = Video(script_id=script.id, status=VideoStatus.approved, file_path=str(fake_video_file))
    db_session.add(video)
    db_session.commit()
    if created_at is not None:
        video.created_at = created_at
        db_session.commit()
    db_session.refresh(video)
    return video


def _make_due_slot(db_session, **overrides) -> PostingSlot:
    now = datetime.utcnow()
    defaults = dict(
        label="test slot",
        days_of_week=[now.weekday()],
        time_of_day=(now - timedelta(minutes=1)).strftime("%H:%M"),
        platforms=None,
        enabled=True,
        last_fired_date=None,
    )
    defaults.update(overrides)
    slot = PostingSlot(**defaults)
    db_session.add(slot)
    db_session.commit()
    db_session.refresh(slot)
    return slot


def _dispatch(db_session):
    with patch("faceless_pipeline.modules.publisher.recurring.SessionLocal", return_value=db_session), patch.object(
        db_session, "close", lambda: None
    ):
        return dispatch_due_posting_slots()


def test_due_slot_publishes_the_oldest_queued_video(db_session, tmp_path):
    older = _make_approved_video(db_session, "Older", tmp_path, created_at=datetime.utcnow() - timedelta(days=1))
    newer = _make_approved_video(db_session, "Newer", tmp_path)
    _make_due_slot(db_session)

    with patch("faceless_pipeline.modules.publisher.run.youtube_upload", return_value="yt-slot-123") as mock_upload:
        fired = _dispatch(db_session)

    assert fired == 1
    mock_upload.assert_called_once()
    db_session.refresh(older)
    db_session.refresh(newer)
    assert older.status == VideoStatus.published
    assert older.platform_ids.get("youtube") == "yt-slot-123"
    assert newer.status == VideoStatus.approved  # untouched - only the oldest was consumed


def test_slot_not_due_today_is_skipped(db_session, tmp_path):
    _make_approved_video(db_session, "Video", tmp_path)
    tomorrow = (datetime.utcnow().weekday() + 1) % 7
    _make_due_slot(db_session, days_of_week=[tomorrow])

    with patch("faceless_pipeline.modules.publisher.run.youtube_upload") as mock_upload:
        fired = _dispatch(db_session)
        mock_upload.assert_not_called()

    assert fired == 0


def test_slot_already_fired_today_does_not_fire_again(db_session, tmp_path):
    video = _make_approved_video(db_session, "Video", tmp_path)
    _make_due_slot(db_session, last_fired_date=datetime.utcnow().date().isoformat())

    with patch("faceless_pipeline.modules.publisher.run.youtube_upload") as mock_upload:
        fired = _dispatch(db_session)
        mock_upload.assert_not_called()

    assert fired == 0
    db_session.refresh(video)
    assert video.status == VideoStatus.approved


def test_disabled_slot_never_fires(db_session, tmp_path):
    _make_approved_video(db_session, "Video", tmp_path)
    _make_due_slot(db_session, enabled=False)

    fired = _dispatch(db_session)

    assert fired == 0


def test_due_slot_with_no_queued_video_marks_fired_without_error(db_session):
    slot = _make_due_slot(db_session)

    fired = _dispatch(db_session)

    assert fired == 1
    db_session.refresh(slot)
    assert slot.last_fired_date == datetime.utcnow().date().isoformat()


def test_individually_scheduled_video_is_not_consumed_by_a_recurring_slot(db_session, tmp_path):
    """A video someone deliberately scheduled for a specific time (via
    approve's scheduled_for) is off-limits to recurring slots, which
    should only draw from the plain "approved and unscheduled" queue."""
    scheduled = _make_approved_video(db_session, "Individually scheduled", tmp_path, created_at=datetime.utcnow() - timedelta(days=1))
    scheduled.scheduled_for = datetime.utcnow() + timedelta(hours=1)
    db_session.commit()
    queued = _make_approved_video(db_session, "Recurring queue video", tmp_path)
    _make_due_slot(db_session)

    with patch("faceless_pipeline.modules.publisher.run.youtube_upload", return_value="yt-queued-1"):
        _dispatch(db_session)

    db_session.refresh(scheduled)
    db_session.refresh(queued)
    assert scheduled.status == VideoStatus.approved  # left alone
    assert queued.status == VideoStatus.published


def test_slot_platforms_override_is_passed_through(db_session, tmp_path):
    _make_approved_video(db_session, "Video", tmp_path)
    _make_due_slot(db_session, platforms=["youtube"])

    with patch("faceless_pipeline.modules.publisher.run.publish_video") as mock_publish:
        mock_publish.return_value.platform_ids = {"youtube": "yt-1"}
        _dispatch(db_session)

    _, kwargs = mock_publish.call_args
    assert kwargs["platforms"] == ["youtube"]


def test_slots_crud_api(db_session):
    from faceless_pipeline.db import get_db

    def _override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db
    try:
        created = client.post(
            "/api/publish/slots",
            json={"label": "Evenings", "days_of_week": [0, 2, 4], "time_of_day": "18:00", "platforms": ["youtube"]},
        )
        assert created.status_code == 200, created.text
        slot_id = created.json()["id"]
        assert created.json()["days_of_week"] == [0, 2, 4]

        listed = client.get("/api/publish/slots").json()
        assert any(s["id"] == slot_id for s in listed)

        updated = client.patch(f"/api/publish/slots/{slot_id}", json={"enabled": False})
        assert updated.status_code == 200
        assert updated.json()["enabled"] is False

        deleted = client.delete(f"/api/publish/slots/{slot_id}")
        assert deleted.status_code == 200
        assert client.get("/api/publish/slots").json() == []
    finally:
        app.dependency_overrides.clear()


def test_create_slot_rejects_invalid_time_format(db_session):
    from faceless_pipeline.db import get_db

    def _override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db
    try:
        resp = client.post("/api/publish/slots", json={"days_of_week": [0], "time_of_day": "6pm"})
        assert resp.status_code == 422
    finally:
        app.dependency_overrides.clear()


def test_create_slot_rejects_empty_days(db_session):
    from faceless_pipeline.db import get_db

    def _override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db
    try:
        resp = client.post("/api/publish/slots", json={"days_of_week": [], "time_of_day": "18:00"})
        assert resp.status_code == 422
    finally:
        app.dependency_overrides.clear()


def test_create_slot_rejects_unknown_platform(db_session):
    from faceless_pipeline.db import get_db

    def _override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db
    try:
        resp = client.post(
            "/api/publish/slots", json={"days_of_week": [0], "time_of_day": "18:00", "platforms": ["facebook"]}
        )
        assert resp.status_code == 422
    finally:
        app.dependency_overrides.clear()


def test_create_slot_accepts_instagram_as_a_platform(db_session):
    from faceless_pipeline.db import get_db

    def _override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db
    try:
        resp = client.post(
            "/api/publish/slots", json={"days_of_week": [0], "time_of_day": "18:00", "platforms": ["instagram"]}
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["platforms"] == ["instagram"]
    finally:
        app.dependency_overrides.clear()


def test_update_slot_can_change_time_days_and_platforms_together(db_session):
    """The edit UI sends a full PATCH (every field, not just the one
    that changed) - covers that update_slot() applies all of them, not
    just the single-field patches (enabled toggle) exercised elsewhere."""
    from faceless_pipeline.db import get_db

    def _override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db
    try:
        created = client.post(
            "/api/publish/slots",
            json={"label": "Old", "days_of_week": [0], "time_of_day": "09:00", "platforms": ["youtube"]},
        ).json()

        updated = client.patch(
            f"/api/publish/slots/{created['id']}",
            json={"label": "New", "days_of_week": [1, 3, 5], "time_of_day": "20:15", "platforms": ["tiktok"]},
        )

        assert updated.status_code == 200, updated.text
        body = updated.json()
        assert body["label"] == "New"
        assert body["days_of_week"] == [1, 3, 5]
        assert body["time_of_day"] == "20:15"
        assert body["platforms"] == ["tiktok"]
    finally:
        app.dependency_overrides.clear()


def test_update_slot_platforms_null_clears_to_auto_detect(db_session):
    from faceless_pipeline.db import get_db

    def _override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db
    try:
        created = client.post(
            "/api/publish/slots", json={"days_of_week": [0], "time_of_day": "09:00", "platforms": ["youtube"]}
        ).json()

        updated = client.patch(f"/api/publish/slots/{created['id']}", json={"platforms": None})

        assert updated.status_code == 200, updated.text
        assert updated.json()["platforms"] is None
    finally:
        app.dependency_overrides.clear()


def test_update_slot_rejects_invalid_time_format(db_session):
    from faceless_pipeline.db import get_db

    def _override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db
    try:
        created = client.post(
            "/api/publish/slots", json={"days_of_week": [0], "time_of_day": "09:00"}
        ).json()

        resp = client.patch(f"/api/publish/slots/{created['id']}", json={"time_of_day": "not-a-time"})

        assert resp.status_code == 422
    finally:
        app.dependency_overrides.clear()


def test_update_slot_rejects_empty_days(db_session):
    from faceless_pipeline.db import get_db

    def _override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db
    try:
        created = client.post(
            "/api/publish/slots", json={"days_of_week": [0], "time_of_day": "09:00"}
        ).json()

        resp = client.patch(f"/api/publish/slots/{created['id']}", json={"days_of_week": []})

        assert resp.status_code == 422
    finally:
        app.dependency_overrides.clear()


def test_update_missing_slot_returns_404(db_session):
    from faceless_pipeline.db import get_db

    def _override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db
    try:
        resp = client.patch("/api/publish/slots/999999", json={"enabled": False})
        assert resp.status_code == 404
    finally:
        app.dependency_overrides.clear()
