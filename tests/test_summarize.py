"""Tests for the summarization layer (Anthropic-API-backed)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from sbo_ingestion.handlers.claude_ai import Conversation, Message
from sbo_ingestion.summarize import Summary, _parse_summary_or_fallback, summarize


def _convo() -> Conversation:
    return Conversation(
        uuid="test-1",
        title="Test conversation",
        created_at="2026-05-11T10:00:00Z",
        updated_at="2026-05-11T10:30:00Z",
        platform="claude.ai",
        messages=(
            Message(uuid="m1", sender="human", text="What's a second brain?", created_at="2026-05-11T10:00:00Z"),
            Message(uuid="m2", sender="assistant", text="A personal knowledge system.", created_at="2026-05-11T10:00:30Z"),
        ),
    )


@patch("sbo_ingestion.summarize.Anthropic")
def test_summarize_returns_summary_object(mock_anthropic_cls: MagicMock) -> None:
    mock_client = MagicMock()
    mock_anthropic_cls.return_value = mock_client
    mock_client.messages.create.return_value = MagicMock(
        content=[MagicMock(text='{"title": "Defining second brain", "tldr": "Personal knowledge system architecture discussion.", "insights": ["A second brain is a personal knowledge system."], "decisions": [], "open_questions": [], "people_mentioned": [], "suggested_destinations": ["notes/learnings/second-brain-definition.md"]}')]
    )
    result = summarize(_convo(), api_key="test-key")
    assert isinstance(result, Summary)
    assert result.title == "Defining second brain"
    assert result.tldr.startswith("Personal knowledge")
    assert len(result.insights) == 1


@patch("sbo_ingestion.summarize.Anthropic")
def test_summarize_calls_with_prompt_caching(mock_anthropic_cls: MagicMock) -> None:
    mock_client = MagicMock()
    mock_anthropic_cls.return_value = mock_client
    mock_client.messages.create.return_value = MagicMock(
        content=[MagicMock(text='{"title": "T", "tldr": "T", "insights": [], "decisions": [], "open_questions": [], "people_mentioned": [], "suggested_destinations": []}')]
    )
    summarize(_convo(), api_key="test-key")
    call_kwargs = mock_client.messages.create.call_args.kwargs
    # The system prompt should be cacheable
    system = call_kwargs.get("system")
    assert system, "system prompt should be set"
    if isinstance(system, list):
        assert any(b.get("cache_control") for b in system), "should request cache_control on at least one system block"


@patch("sbo_ingestion.summarize.Anthropic")
def test_summarize_handles_malformed_response(mock_anthropic_cls: MagicMock) -> None:
    mock_client = MagicMock()
    mock_anthropic_cls.return_value = mock_client
    mock_client.messages.create.return_value = MagicMock(content=[MagicMock(text="not json")])
    # Should return a degraded Summary, not raise
    result = summarize(_convo(), api_key="test-key")
    assert isinstance(result, Summary)
    assert result.title == "Test conversation"  # falls back to the convo title
    assert "could not be parsed" in result.tldr.lower() or result.tldr == ""


@pytest.mark.parametrize("text", ["[]", '"just a string"', "null", "42"])
def test_parse_valid_json_that_is_not_an_object_falls_back(text: str) -> None:
    result = _parse_summary_or_fallback(text, fallback_title="Fallback")
    assert result.title == "Fallback"
    assert "could not be parsed" in result.tldr.lower()


def test_parse_string_list_field_is_one_item_not_characters() -> None:
    result = _parse_summary_or_fallback(
        '{"title": "T", "tldr": "x", "insights": "One complete insight."}',
        fallback_title="Fallback",
    )
    assert result.insights == ("One complete insight.",)


def test_parse_ignores_wrong_typed_fields() -> None:
    result = _parse_summary_or_fallback(
        '{"title": 7, "tldr": ["a"], "insights": [{"a": 1}, "kept", 3, null],'
        ' "decisions": null, "open_questions": 5, "people_mentioned": null,'
        ' "suggested_destinations": 5}',
        fallback_title="Fallback",
    )
    assert result.title == "Fallback"
    assert result.tldr == ""
    assert result.insights == ("kept",)
    assert result.decisions == ()
    assert result.open_questions == ()
    assert result.people_mentioned == ()
    assert result.suggested_destinations == ()


def test_parse_people_need_a_string_name() -> None:
    result = _parse_summary_or_fallback(
        '{"people_mentioned": [{"name": "Ada", "context": "mentor"}, {"name": 5}, {"name": "Bo", "context": null}, "Cy"]}',
        fallback_title="Fallback",
    )
    assert [(p.name, p.context) for p in result.people_mentioned] == [("Ada", "mentor"), ("Bo", "")]
