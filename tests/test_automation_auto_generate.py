"""auto_generate_from_trends(): picks top unused trends by score and
generates+assembles a script/video for each, closing trend -> script ->
video with no human topic pick. Also covers choose_style()'s epsilon-
greedy bias toward the historically best-performing style.
"""
from unittest.mock import patch

from faceless_pipeline.config import settings
from faceless_pipeline.models import Performance, Script, Trend, Video, VideoStatus
from faceless_pipeline.modules.automation.run import auto_generate_from_trends, choose_style

FAKE_SCRIPT_JSON = '{"hook": "h", "promise": "p", "body": "body text here", "payoff": "pa", "cta": "c"}'


class _FakeBlock:
    type = "text"
    text = FAKE_SCRIPT_JSON


class _FakeMessage:
    content = [_FakeBlock()]

    class usage:
        input_tokens = 100
        output_tokens = 50


def _add_trend(db_session, topic: str, score: float, used: bool = False) -> Trend:
    trend = Trend(topic=topic, normalized_topic=topic.lower(), source="google_trends", score=score, used=used)
    db_session.add(trend)
    db_session.commit()
    db_session.refresh(trend)
    return trend


def test_auto_generate_picks_top_unused_trends_by_score(db_session):
    _add_trend(db_session, "Low score topic", score=10.0)
    _add_trend(db_session, "High score topic", score=90.0)
    _add_trend(db_session, "Already used topic", score=99.0, used=True)

    with patch("anthropic.Anthropic") as mock_client:
        mock_client.return_value.messages.create.return_value = _FakeMessage()
        generated = auto_generate_from_trends(db_session, count=1, min_score=0)

    assert len(generated) == 1
    assert generated[0].topic == "High score topic"

    used_trend = db_session.query(Trend).filter(Trend.topic == "High score topic").first()
    assert used_trend.used is True


def test_auto_generate_respects_min_score_threshold(db_session):
    _add_trend(db_session, "Below threshold", score=5.0)

    with patch("anthropic.Anthropic") as mock_client:
        mock_client.return_value.messages.create.return_value = _FakeMessage()
        generated = auto_generate_from_trends(db_session, count=5, min_score=50.0)

    assert generated == []


def test_auto_generate_creates_a_pending_video_per_script(db_session):
    _add_trend(db_session, "Video creation topic", score=80.0)

    with patch("anthropic.Anthropic") as mock_client:
        mock_client.return_value.messages.create.return_value = _FakeMessage()
        generated = auto_generate_from_trends(db_session, count=1, min_score=0)

    assert len(generated) == 1
    video = db_session.query(Video).filter(Video.script_id == generated[0].id).first()
    assert video is not None
    assert video.status == VideoStatus.pending


def test_auto_generate_skips_a_trend_that_already_has_a_script(db_session):
    script = Script(topic="Existing topic", script={"hook": "h"}, status="draft")
    db_session.add(script)
    db_session.commit()
    _add_trend(db_session, "Existing topic", score=99.0)

    with patch("anthropic.Anthropic") as mock_client:
        mock_client.return_value.messages.create.return_value = _FakeMessage()
        generated = auto_generate_from_trends(db_session, count=1, min_score=0)

    assert generated == []
    # Marked used so it doesn't get re-selected forever.
    trend = db_session.query(Trend).filter(Trend.topic == "Existing topic").first()
    assert trend.used is True


def test_auto_generate_one_failure_does_not_block_the_rest_of_the_batch(db_session):
    _add_trend(db_session, "Will fail topic", score=99.0)
    _add_trend(db_session, "Will succeed topic", score=50.0)

    call_count = {"n": 0}

    def _create(*args, **kwargs):
        call_count["n"] += 1
        if call_count["n"] == 1:
            raise RuntimeError("simulated provider failure")
        return _FakeMessage()

    with patch("anthropic.Anthropic") as mock_client:
        mock_client.return_value.messages.create.side_effect = _create
        generated = auto_generate_from_trends(db_session, count=2, min_score=0)

    assert len(generated) == 1
    assert generated[0].topic == "Will succeed topic"


def test_choose_style_disabled_returns_configured_default(db_session):
    original = settings.ab_test_enabled
    settings.ab_test_enabled = False
    try:
        assert choose_style(db_session) == settings.auto_generate_style
    finally:
        settings.ab_test_enabled = original


def test_choose_style_exploits_best_performing_style_when_enabled(db_session):
    original_enabled, original_styles = settings.ab_test_enabled, settings.ab_test_styles
    settings.ab_test_enabled = True
    settings.ab_test_styles = "explainer,listicle"
    try:
        script_a = Script(topic="A", script={}, style="explainer", status="draft")
        script_b = Script(topic="B", script={}, style="listicle", status="draft")
        db_session.add_all([script_a, script_b])
        db_session.commit()

        video_a = Video(script_id=script_a.id, status=VideoStatus.published)
        video_b = Video(script_id=script_b.id, status=VideoStatus.published)
        db_session.add_all([video_a, video_b])
        db_session.commit()

        db_session.add(Performance(video_id=video_a.id, platform="youtube", views=100))
        db_session.add(Performance(video_id=video_b.id, platform="youtube", views=9000))
        db_session.commit()

        with patch("random.random", return_value=0.99):  # force exploitation, not exploration
            assert choose_style(db_session) == "listicle"
    finally:
        settings.ab_test_enabled, settings.ab_test_styles = original_enabled, original_styles


def test_choose_style_explores_randomly_at_the_configured_rate(db_session):
    original_enabled, original_styles = settings.ab_test_enabled, settings.ab_test_styles
    settings.ab_test_enabled = True
    settings.ab_test_styles = "explainer,listicle"
    try:
        with patch("random.random", return_value=0.01), patch("random.choice", return_value="listicle") as mock_choice:
            result = choose_style(db_session)
        mock_choice.assert_called_once()
        assert result == "listicle"
    finally:
        settings.ab_test_enabled, settings.ab_test_styles = original_enabled, original_styles
