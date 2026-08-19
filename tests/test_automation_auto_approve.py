"""maybe_auto_approve(): opt-in (AUTO_APPROVE_ENABLED, off by default) —
skips the human review click for a video that passes basic safety
checks, immediately approving and publishing it.
"""
from unittest.mock import patch

from faceless_pipeline.config import settings
from faceless_pipeline.models import Script, Video, VideoStatus
from faceless_pipeline.modules.automation.auto_approve import maybe_auto_approve, passes_auto_approve_checks

_FULL_STORYBOARD = [
    {"beat": b, "visual": "v", "keywords": ["k"]} for b in ["hook", "promise", "body", "payoff", "cta"]
]


def _make_video(db_session, tmp_path, storyboard=_FULL_STORYBOARD, with_file=True) -> Video:
    script = Script(
        topic="Auto approve test",
        script={"hook": "h", "promise": "p", "body": "b", "payoff": "pa", "cta": "c", "storyboard": storyboard},
        status="draft",
    )
    db_session.add(script)
    db_session.commit()
    db_session.refresh(script)

    file_path = None
    if with_file:
        f = tmp_path / "video.mp4"
        f.write_bytes(b"fake")
        file_path = str(f)

    video = Video(script_id=script.id, status=VideoStatus.pending, file_path=file_path)
    db_session.add(video)
    db_session.commit()
    db_session.refresh(video)
    return video


def test_disabled_by_default_is_a_noop(db_session, tmp_path):
    assert settings.auto_approve_enabled is False
    video = _make_video(db_session, tmp_path)

    result = maybe_auto_approve(db_session, video.id)

    assert result is False
    db_session.refresh(video)
    assert video.status == VideoStatus.pending


def test_passes_checks_approves_and_publishes(db_session, tmp_path):
    video = _make_video(db_session, tmp_path)
    original = settings.auto_approve_enabled
    settings.auto_approve_enabled = True
    try:
        with patch("faceless_pipeline.modules.publisher.run.publish_video") as mock_publish:
            mock_publish.return_value = video
            result = maybe_auto_approve(db_session, video.id)
    finally:
        settings.auto_approve_enabled = original

    assert result is True
    db_session.refresh(video)
    assert video.status == VideoStatus.approved
    mock_publish.assert_called_once()


def test_no_rendered_file_fails_the_check(db_session, tmp_path):
    video = _make_video(db_session, tmp_path, with_file=False)
    original = settings.auto_approve_enabled
    settings.auto_approve_enabled = True
    try:
        result = maybe_auto_approve(db_session, video.id)
    finally:
        settings.auto_approve_enabled = original

    assert result is False
    db_session.refresh(video)
    assert video.status == VideoStatus.pending


def test_incomplete_storyboard_fails_the_check(db_session, tmp_path):
    video = _make_video(db_session, tmp_path, storyboard=_FULL_STORYBOARD[:2])
    passed, reason = passes_auto_approve_checks(video)

    assert passed is False
    assert "storyboard" in reason


def test_already_approved_video_is_a_noop(db_session, tmp_path):
    video = _make_video(db_session, tmp_path)
    video.status = VideoStatus.approved
    db_session.commit()

    original = settings.auto_approve_enabled
    settings.auto_approve_enabled = True
    try:
        result = maybe_auto_approve(db_session, video.id)
    finally:
        settings.auto_approve_enabled = original

    assert result is False
