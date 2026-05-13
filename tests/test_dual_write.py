"""Tests for dual_write — writes raw to private/, summary to brain/_inbox/."""

from __future__ import annotations

from pathlib import Path

import frontmatter

from sbo_ingestion.dual_write import DualWriteResult, write_pair
from sbo_ingestion.handlers.claude_ai import Conversation, Message
from sbo_ingestion.summarize import PersonMention, Summary


def _convo() -> Conversation:
    return Conversation(
        uuid="abc-123",
        title="Test conversation",
        created_at="2026-05-11T10:00:00Z",
        updated_at="2026-05-11T10:30:00Z",
        platform="claude.ai",
        messages=(
            Message(uuid="m1", sender="human", text="Hi", created_at="2026-05-11T10:00:00Z"),
            Message(uuid="m2", sender="assistant", text="Hello", created_at="2026-05-11T10:00:30Z"),
        ),
    )


def _summary() -> Summary:
    return Summary(
        title="Greeting exchange",
        tldr="A test conversation.",
        insights=("Test insight.",),
        decisions=(),
        open_questions=("What next?",),
        people_mentioned=(PersonMention(name="Jane Doe", context="mentioned as collaborator"),),
        suggested_destinations=("notes/learnings/greeting.md",),
    )


def test_write_pair_creates_both_files(tmp_vault_pair: tuple[Path, Path]) -> None:
    brain, private = tmp_vault_pair
    result = write_pair(_convo(), _summary(), brain_root=brain, private_root=private)
    assert isinstance(result, DualWriteResult)
    assert result.private_path.exists()
    assert result.brain_path.exists()


def test_private_file_has_correct_path_shape(tmp_vault_pair: tuple[Path, Path]) -> None:
    brain, private = tmp_vault_pair
    result = write_pair(_convo(), _summary(), brain_root=brain, private_root=private)
    rel = result.private_path.relative_to(private)
    assert rel.parts[0] == "chat-history"
    assert rel.parts[1] == "claude-ai"
    assert "2026-05-11" in rel.parts[2]
    assert "abc-123" in rel.parts[2]
    assert rel.parts[2].endswith(".md")


def test_brain_file_has_correct_path_shape(tmp_vault_pair: tuple[Path, Path]) -> None:
    brain, private = tmp_vault_pair
    result = write_pair(_convo(), _summary(), brain_root=brain, private_root=private)
    rel = result.brain_path.relative_to(brain)
    assert rel.parts[0] == "_inbox"
    assert rel.parts[1] == "claude-ai"
    assert "2026-05-11" in rel.parts[2]


def test_private_file_contains_raw_content(tmp_vault_pair: tuple[Path, Path]) -> None:
    brain, private = tmp_vault_pair
    result = write_pair(_convo(), _summary(), brain_root=brain, private_root=private)
    post = frontmatter.load(result.private_path)
    assert post.metadata["source"] == "claude.ai"
    assert post.metadata["conversation_id"] == "abc-123"
    assert post.metadata["title"] == "Test conversation"
    assert "Hi" in post.content
    assert "Hello" in post.content


def test_brain_file_contains_summary_sections(tmp_vault_pair: tuple[Path, Path]) -> None:
    brain, private = tmp_vault_pair
    result = write_pair(_convo(), _summary(), brain_root=brain, private_root=private)
    text = result.brain_path.read_text(encoding="utf-8")
    assert "**TL;DR:**" in text
    assert "## Insights" in text
    assert "## Open questions" in text
    assert "## People mentioned" in text
    assert "Jane Doe" in text


def test_brain_file_links_to_private(tmp_vault_pair: tuple[Path, Path]) -> None:
    brain, private = tmp_vault_pair
    result = write_pair(_convo(), _summary(), brain_root=brain, private_root=private)
    post = frontmatter.load(result.brain_path)
    assert "private_file" in post.metadata
    assert "claude-ai" in post.metadata["private_file"]


def test_brain_frontmatter_status_is_triage(tmp_vault_pair: tuple[Path, Path]) -> None:
    brain, private = tmp_vault_pair
    result = write_pair(_convo(), _summary(), brain_root=brain, private_root=private)
    post = frontmatter.load(result.brain_path)
    assert post.metadata["status"] == "triage"
    assert "needs-triage" in post.metadata["tags"]
