"""Regression test: published videos must actually get tags/hashtags.

Bug: write_metadata()'s `tags` parameter defaulted to None -> [] and
video/run.py's one call site never passed anything for it, so every
published video's metadata.json had "tags": [] regardless of content.
That flowed straight through to publish time - youtube_upload() sends
tags=metadata.get("tags", []) (always empty) and TikTok's caption-hashtag
logic in tiktok.py (`f"#{t}"` per tag) never had any tags to work with
either, so real videos published with zero tags and zero hashtags despite
the storyboard already generating exactly the right search keywords per
beat for this. Fixed by deriving tags from the storyboard's keywords when
the caller doesn't supply an explicit list.
"""
import json

from faceless_pipeline.modules.video.metadata import tags_from_storyboard, write_metadata


def test_write_metadata_derives_tags_from_storyboard_keywords(tmp_path):
    script_json = {
        "hook": "h",
        "promise": "p",
        "body": "b",
        "payoff": "pa",
        "cta": "c",
        "storyboard": [
            {"beat": "hook", "visual": "v", "keywords": ["capybara", "onsen"]},
            {"beat": "promise", "visual": "v", "keywords": ["relaxation"]},
        ],
    }
    out_path = str(tmp_path / "metadata.json")

    write_metadata(script_json, "Capybara facts", out_path)

    metadata = json.loads((tmp_path / "metadata.json").read_text())
    assert metadata["tags"] == ["capybara", "onsen", "relaxation"]


def test_tags_from_storyboard_dedupes_case_insensitively():
    script_json = {
        "storyboard": [
            {"beat": "hook", "keywords": ["Capybara", "Onsen"]},
            {"beat": "promise", "keywords": ["capybara", "relaxation"]},
        ]
    }

    tags = tags_from_storyboard(script_json)

    assert tags == ["Capybara", "Onsen", "relaxation"]


def test_write_metadata_with_no_storyboard_gets_empty_tags_not_a_crash(tmp_path):
    out_path = str(tmp_path / "metadata.json")

    write_metadata({"hook": "h"}, "Old-style script", out_path)

    metadata = json.loads((tmp_path / "metadata.json").read_text())
    assert metadata["tags"] == []


def test_write_metadata_respects_an_explicit_empty_tags_opt_out(tmp_path):
    script_json = {"storyboard": [{"beat": "hook", "keywords": ["capybara"]}]}
    out_path = str(tmp_path / "metadata.json")

    write_metadata(script_json, "Topic", out_path, tags=[])

    metadata = json.loads((tmp_path / "metadata.json").read_text())
    assert metadata["tags"] == []


def test_tags_from_storyboard_respects_max_tags_cap():
    script_json = {"storyboard": [{"beat": "hook", "keywords": [f"kw{i}" for i in range(30)]}]}

    tags = tags_from_storyboard(script_json, max_tags=5)

    assert len(tags) == 5
