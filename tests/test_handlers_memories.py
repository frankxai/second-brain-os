"""Tests for the memories.json handler — the AI's cross-conversation memory export."""

from __future__ import annotations

from pathlib import Path

import frontmatter

from sbo_ingestion.handlers.memories import (
    extract_memories,
    parse_memories,
    write_memory_export,
)


def test_parse_memories_list_shape(memories_list_path: Path) -> None:
    """Top-level-list export: text/content keys and bare strings all flatten."""
    mems = parse_memories(memories_list_path)
    assert len(mems) == 3
    assert any("two-vault" in m for m in mems)
    assert "Ships open-source tooling under the MIT license." in mems


def test_parse_memories_dict_shape(memories_dict_path: Path) -> None:
    """Wrapper-dict export ({"memories": [...]}) flattens to the same shape."""
    mems = parse_memories(memories_dict_path)
    assert len(mems) == 3
    assert any("two-vault" in m for m in mems)


def test_extract_memories_flat_dict_facts() -> None:
    """A flat {key: value} dict with no wrapper list renders as `key: value` lines."""
    mems = extract_memories({"name_pref": "goes by first name", "timezone": "UTC+1"})
    assert "name_pref: goes by first name" in mems
    assert "timezone: UTC+1" in mems


def test_extract_memories_tolerates_bad_shapes() -> None:
    assert extract_memories(None) == []
    assert extract_memories(42) == []
    assert extract_memories("a single memory string") == ["a single memory string"]


def test_write_memory_export_creates_file(
    memories_list_path: Path, tmp_vault_pair: tuple[Path, Path]
) -> None:
    brain, _ = tmp_vault_pair
    result = write_memory_export(memories_list_path, brain_root=brain)
    assert result.brain_path.exists()
    assert result.brain_path.name == "_memory-export.md"
    assert result.brain_path.parent == brain / "_inbox" / "claude-ai"
    assert result.memory_count == 3


def test_memory_export_frontmatter_and_header(
    memories_list_path: Path, tmp_vault_pair: tuple[Path, Path]
) -> None:
    """The file flags itself as high-signal and tells agents to weight it heavily."""
    brain, _ = tmp_vault_pair
    result = write_memory_export(memories_list_path, brain_root=brain)
    post = frontmatter.load(result.brain_path)
    assert post.metadata["kind"] == "memory-export"
    assert post.metadata["weight"] == "high"
    assert post.metadata["memory_count"] == 3
    assert "weight these memories heavily" in post.content.lower()
    assert "Ships open-source tooling under the MIT license." in post.content
