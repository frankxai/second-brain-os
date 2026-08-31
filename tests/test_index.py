"""Tests for the _INDEX.md corpus-map emitter."""

from __future__ import annotations

from pathlib import Path

import frontmatter

from sbo_ingestion.dual_write import write_index
from sbo_ingestion.handlers.claude_ai import Conversation


def _convo(uuid: str, title: str, created: str, summary: str = "") -> Conversation:
    return Conversation(
        uuid=uuid,
        title=title,
        created_at=created,
        updated_at=created,
        platform="claude.ai",
        summary=summary,
        messages=(),
    )


def test_write_index_creates_file(tmp_vault_pair: tuple[Path, Path]) -> None:
    brain, _ = tmp_vault_pair
    convos = [_convo("a", "Alpha", "2026-05-10T10:00:00Z", "first summary")]
    index_path = write_index(convos, brain_root=brain, platform="claude.ai")
    assert index_path.exists()
    assert index_path.name == "_INDEX.md"
    assert index_path.parent == brain / "_inbox" / "claude-ai"


def test_index_is_newest_first(tmp_vault_pair: tuple[Path, Path]) -> None:
    brain, _ = tmp_vault_pair
    convos = [
        _convo("old", "Older chat", "2026-05-10T10:00:00Z"),
        _convo("new", "Newer chat", "2026-05-12T10:00:00Z"),
    ]
    index_path = write_index(convos, brain_root=brain, platform="claude.ai")
    body = index_path.read_text(encoding="utf-8")
    assert body.index("Newer chat") < body.index("Older chat")


def test_index_has_table_and_summary_column(tmp_vault_pair: tuple[Path, Path]) -> None:
    brain, _ = tmp_vault_pair
    convos = [_convo("a", "Alpha", "2026-05-10T10:00:00Z", "the export summary")]
    index_path = write_index(convos, brain_root=brain, platform="claude.ai")
    post = frontmatter.load(index_path)
    assert post.metadata["kind"] == "inbox-index"
    assert post.metadata["conversation_count"] == 1
    assert "| Date | Title | Summary |" in post.content
    assert "2026-05-10" in post.content
    assert "the export summary" in post.content


def test_index_escapes_pipes_in_cells(tmp_vault_pair: tuple[Path, Path]) -> None:
    """A title/summary containing `|` must not break the markdown table row."""
    brain, _ = tmp_vault_pair
    convos = [_convo("a", "Title with | pipe", "2026-05-10T10:00:00Z", "line1\nline2")]
    index_path = write_index(convos, brain_root=brain, platform="claude.ai")
    body = index_path.read_text(encoding="utf-8")
    assert "Title with \\| pipe" in body
    assert "line1 line2" in body  # newline collapsed to a space
