"""Tests for ChatGPT conversations.json export parser."""

from __future__ import annotations

import json
from pathlib import Path
from zipfile import ZipFile

import pytest

from sbo_ingestion.handlers.chatgpt import conversation_members, parse_export


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


def test_invalid_export_timestamps_do_not_abort_the_conversation(
    chatgpt_export_path: Path, tmp_path: Path
) -> None:
    source = json.loads(chatgpt_export_path.read_text(encoding="utf-8"))
    source[0]["create_time"] = 1e100
    source[0]["update_time"] = "not-a-timestamp"
    for node in source[0]["mapping"].values():
        if node.get("message"):
            node["message"]["create_time"] = 1e100
    export_path = tmp_path / "invalid-timestamps.json"
    export_path.write_text(json.dumps(source), encoding="utf-8")

    conversation = next(parse_export(export_path))

    assert conversation.uuid == "conv-aaaa-1111"
    assert conversation.created_at == ""
    assert conversation.updated_at == ""
    assert all(message.created_at == "" for message in conversation.messages)


def test_to_raw_markdown_renders(chatgpt_export_path: Path) -> None:
    convo = next(parse_export(chatgpt_export_path))
    md = convo.to_raw_markdown()
    assert "# Testing SBO with ChatGPT" in md
    assert "**human**" in md
    assert "**assistant**" in md


def test_parse_export_reads_numbered_zip_shards(
    chatgpt_export_path: Path, tmp_path: Path
) -> None:
    source = json.loads(chatgpt_export_path.read_text(encoding="utf-8"))
    second = dict(source[0])
    second["id"] = "conv-bbbb-2222"
    second["title"] = "Second shard"
    export_zip = tmp_path / "chatgpt-export.zip"
    with ZipFile(export_zip, "w") as archive:
        archive.writestr("conversations-001.json", json.dumps([second]))
        archive.writestr("conversations-000.json", json.dumps(source))
        archive.writestr("shared_conversations.json", "[]")

    convos = list(parse_export(export_zip))

    assert [convo.uuid for convo in convos] == [
        "conv-aaaa-1111",
        "conv-bbbb-2222",
    ]


def test_parse_export_rejects_mixed_legacy_and_shards(
    chatgpt_export_path: Path, tmp_path: Path
) -> None:
    payload = chatgpt_export_path.read_text(encoding="utf-8")
    export_zip = tmp_path / "legacy-export.zip"
    with ZipFile(export_zip, "w") as archive:
        archive.writestr("conversations.json", payload)
        archive.writestr("conversations-000.json", "[]")

    with pytest.raises(ValueError, match="Ambiguous"):
        list(parse_export(export_zip))


def test_parse_export_rejects_gapped_shards(
    chatgpt_export_path: Path, tmp_path: Path
) -> None:
    payload = chatgpt_export_path.read_text(encoding="utf-8")
    export_zip = tmp_path / "gapped-export.zip"
    with ZipFile(export_zip, "w") as archive:
        archive.writestr("conversations-000.json", payload)
        archive.writestr("conversations-002.json", payload)

    with pytest.raises(ValueError, match="Incomplete"):
        conversation_members(export_zip)


def test_parse_export_rejects_duplicate_shard_indexes(
    chatgpt_export_path: Path, tmp_path: Path
) -> None:
    payload = chatgpt_export_path.read_text(encoding="utf-8")
    export_zip = tmp_path / "duplicate-shard-export.zip"
    with ZipFile(export_zip, "w") as archive:
        archive.writestr("conversations-0.json", payload)
        archive.writestr("conversations-000.json", payload)

    with pytest.raises(ValueError, match="duplicate numbered shard"):
        conversation_members(export_zip)


def test_parse_export_rejects_nested_conversation_member(
    chatgpt_export_path: Path, tmp_path: Path
) -> None:
    payload = chatgpt_export_path.read_text(encoding="utf-8")
    export_zip = tmp_path / "nested-export.zip"
    with ZipFile(export_zip, "w") as archive:
        archive.writestr("nested/conversations-000.json", payload)

    with pytest.raises(ValueError, match="ZIP root"):
        conversation_members(export_zip)


def test_parse_export_rejects_duplicate_ids_across_shards(
    chatgpt_export_path: Path, tmp_path: Path
) -> None:
    payload = chatgpt_export_path.read_text(encoding="utf-8")
    export_zip = tmp_path / "duplicate-id-export.zip"
    with ZipFile(export_zip, "w") as archive:
        archive.writestr("conversations-000.json", payload)
        archive.writestr("conversations-001.json", payload)

    with pytest.raises(ValueError, match="Duplicate conversation ID"):
        list(parse_export(export_zip))
