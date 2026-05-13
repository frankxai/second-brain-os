"""Tests for ChatGPT conversations.json export parser."""

from __future__ import annotations

from pathlib import Path

from sbo_ingestion.handlers.chatgpt import parse_export


def test_parse_export_returns_one_conversation(chatgpt_export_path: Path) -> None:
    convos = list(parse_export(chatgpt_export_path))
    assert len(convos) == 1


def test_conversation_metadata(chatgpt_export_path: Path) -> None:
    convo = next(parse_export(chatgpt_export_path))
    assert convo.uuid == "conv-aaaa-1111"
    assert convo.title == "Testing SBO with ChatGPT"
    assert convo.platform == "chatgpt"
    # create_time is unix epoch float; the parser converts to ISO 8601
    assert convo.created_at.startswith("2026-05-11")


def test_conversation_messages_are_in_order(chatgpt_export_path: Path) -> None:
    convo = next(parse_export(chatgpt_export_path))
    assert len(convo.messages) == 2
    assert convo.messages[0].sender == "human"
    assert convo.messages[0].text.startswith("How do I export")
    assert convo.messages[1].sender == "assistant"
    assert "conversations.json" in convo.messages[1].text


def test_to_raw_markdown_renders(chatgpt_export_path: Path) -> None:
    convo = next(parse_export(chatgpt_export_path))
    md = convo.to_raw_markdown()
    assert "# Testing SBO with ChatGPT" in md
    assert "**human**" in md
    assert "**assistant**" in md
