from unittest.mock import patch

import pytest

from app.modules.scripts.generator import generate_script, has_existing_script, regenerate_with_feedback

FAKE_SCRIPT_JSON = (
    '{"hook": "Did you know...", "promise": "I will show you", '
    '"body": "Here is the thing", "payoff": "Mind blown", "cta": "Follow for more"}'
)


class _FakeBlock:
    type = "text"
    text = FAKE_SCRIPT_JSON


class _FakeMessage:
    content = [_FakeBlock()]


@pytest.fixture()
def mock_anthropic():
    with patch("anthropic.Anthropic") as mock_client:
        mock_client.return_value.messages.create.return_value = _FakeMessage()
        yield mock_client


def test_generate_script_creates_structured_script(db_session, mock_anthropic):
    script = generate_script(db_session, topic="Weird history facts", style="story", length_variant="15s")

    assert script.script["hook"] == "Did you know..."
    assert script.style == "story"
    assert script.length_variant == "15s"
    assert has_existing_script(db_session, "Weird history facts") is True


def test_generate_script_blocks_duplicate_topic_by_default(db_session, mock_anthropic):
    generate_script(db_session, topic="Weird history facts")

    with pytest.raises(ValueError):
        generate_script(db_session, topic="Weird history facts")


def test_regenerate_with_feedback_supersedes_original(db_session, mock_anthropic):
    original = generate_script(db_session, topic="Weird history facts")

    new_script = regenerate_with_feedback(db_session, original.id, "Make the hook punchier")

    db_session.refresh(original)
    assert original.status == "superseded"
    assert new_script.parent_script_id == original.id
    assert new_script.feedback_note == "Make the hook punchier"
