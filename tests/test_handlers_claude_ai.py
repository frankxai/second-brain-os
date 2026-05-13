"""Tests for Claude.ai JSONL export parser."""

from __future__ import annotations

from pathlib import Path

from sbo_ingestion.handlers.claude_ai import Conversation, Message, parse_export


def test_parse_export_returns_two_conversations(claude_ai_export_path: Path) -> None:
    convos = list(parse_export(claude_ai_export_path))
    assert len(convos) == 2


def test_first_conversation_has_correct_metadata(claude_ai_export_path: Path) -> None:
    convos = list(parse_export(claude_ai_export_path))
    first = convos[0]
    assert first.uuid == "11111111-1111-1111-1111-111111111111"
    assert first.title == "Designing a second brain"
    assert first.created_at == "2026-05-10T10:00:00.000000+00:00"
    assert first.platform == "claude.ai"


def test_first_conversation_has_four_messages(claude_ai_export_path: Path) -> None:
    convos = list(parse_export(claude_ai_export_path))
    first = convos[0]
    assert len(first.messages) == 4
    assert first.messages[0].sender == "human"
    assert first.messages[0].text.startswith("What's the right structure")
    assert first.messages[1].sender == "assistant"


def test_conversation_to_markdown_renders_messages(
    claude_ai_export_path: Path,
) -> None:
    convos = list(parse_export(claude_ai_export_path))
    first = convos[0]
    md = first.to_raw_markdown()
    assert "# Designing a second brain" in md
    assert "**human**" in md
    assert "**assistant**" in md
    assert "Hard filesystem separation" in md


def test_short_conversation_parses_correctly(claude_ai_export_path: Path) -> None:
    convos = list(parse_export(claude_ai_export_path))
    second = convos[1]
    assert second.title == "Quick question about MCP"
    assert len(second.messages) == 2


def test_message_is_immutable() -> None:
    msg = Message(uuid="x", sender="human", text="hi", created_at="2026-05-11T00:00:00Z")
    try:
        msg.text = "bye"
    except (AttributeError, Exception):
        pass
    else:
        raise AssertionError("Message should be frozen / immutable")
