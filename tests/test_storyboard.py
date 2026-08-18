"""Module 2's storyboard: extends the same Claude call that already
writes the script to also plan what's on screen per beat (hook/promise/
body/payoff/cta), so faceless videos aren't stuck showing one static
background for the whole runtime. No extra API call — one script
generation already requires Claude, so this rides along in the same
response instead of adding a second dependency.

Covers the three shapes a model response can come in: well-formed,
missing the field entirely, and malformed — the latter two must degrade
to a generated default instead of losing the whole script over a
formatting slip.
"""
from unittest.mock import patch

from faceless_pipeline.modules.scripts.generator import STORYBOARD_BEATS, generate_script


class _FakeBlock:
    type = "text"

    def __init__(self, text):
        self.text = text


class _FakeMessage:
    def __init__(self, text):
        self.content = [_FakeBlock(text)]


def _mock_claude(text):
    return patch("anthropic.Anthropic", **{"return_value.messages.create.return_value": _FakeMessage(text)})


def test_well_formed_storyboard_passes_through(db_session):
    text = (
        '{"hook": "h", "promise": "p", "body": "b", "payoff": "pa", "cta": "c", '
        '"storyboard": ['
        '{"beat": "hook", "visual": "close-up of waves", "keywords": ["ocean", "waves"]},'
        '{"beat": "promise", "visual": "aerial descent", "keywords": ["aerial", "ocean"]},'
        '{"beat": "body", "visual": "deep sea creatures", "keywords": ["deep sea"]},'
        '{"beat": "payoff", "visual": "wide sunset shot", "keywords": ["sunset"]},'
        '{"beat": "cta", "visual": "gradient with text", "keywords": ["abstract"]}'
        ']}'
    )
    with _mock_claude(text):
        script = generate_script(db_session, topic="Storyboard well-formed test")

    storyboard = script.script["storyboard"]
    assert len(storyboard) == 5
    assert [shot["beat"] for shot in storyboard] == STORYBOARD_BEATS
    assert storyboard[0]["visual"] == "close-up of waves"
    assert storyboard[0]["keywords"] == ["ocean", "waves"]


def test_missing_storyboard_gets_a_default(db_session):
    text = '{"hook": "h", "promise": "p", "body": "b", "payoff": "pa", "cta": "c"}'
    with _mock_claude(text):
        script = generate_script(db_session, topic="Storyboard missing test")

    storyboard = script.script["storyboard"]
    assert len(storyboard) == 5
    assert [shot["beat"] for shot in storyboard] == STORYBOARD_BEATS
    assert all(shot["visual"] for shot in storyboard)
    assert all(shot["keywords"] for shot in storyboard)


def test_malformed_storyboard_shot_gets_a_default_for_that_beat(db_session):
    text = (
        '{"hook": "h", "promise": "p", "body": "b", "payoff": "pa", "cta": "c", '
        '"storyboard": ['
        '{"beat": "hook", "visual": "close-up of waves", "keywords": ["ocean"]},'
        '{"beat": "promise"},'  # missing "visual" - malformed
        '{"beat": "body", "visual": "deep sea creatures", "keywords": ["deep sea"]},'
        '{"beat": "payoff", "visual": "wide sunset shot", "keywords": ["sunset"]},'
        '{"beat": "cta", "visual": "gradient with text", "keywords": ["abstract"]}'
        ']}'
    )
    with _mock_claude(text):
        script = generate_script(db_session, topic="Storyboard malformed test")

    storyboard = script.script["storyboard"]
    assert len(storyboard) == 5
    assert storyboard[0]["visual"] == "close-up of waves"  # untouched
    assert storyboard[1]["beat"] == "promise"
    assert storyboard[1]["visual"]  # filled in by the default, not empty/missing
