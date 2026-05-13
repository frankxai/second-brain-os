"""End-to-end ingestion test with mocked summarizer."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from sbo_ingestion.ingest import ingest
from sbo_ingestion.summarize import Summary


@patch("sbo_ingestion.ingest.summarize")
def test_ingest_claude_ai_writes_two_pairs(
    mock_summarize: MagicMock,
    claude_ai_export_path: Path,
    tmp_vault_pair: tuple[Path, Path],
) -> None:
    brain, private = tmp_vault_pair
    mock_summarize.return_value = Summary(title="Test", tldr="t", insights=("i",))
    result = ingest(claude_ai_export_path, brain_root=brain, private_root=private, api_key="test")
    # Fixture has 2 conversations
    assert len(result) == 2
    # Both raw files exist in private/
    raw_files = list((private / "chat-history" / "claude-ai").glob("*.md"))
    assert len(raw_files) == 2
    # Both brain files exist in _inbox/
    brain_files = list((brain / "_inbox" / "claude-ai").glob("*.md"))
    assert len(brain_files) == 2


@patch("sbo_ingestion.ingest.summarize")
def test_ingest_chatgpt_routes_correctly(
    mock_summarize: MagicMock,
    chatgpt_export_path: Path,
    tmp_vault_pair: tuple[Path, Path],
) -> None:
    brain, private = tmp_vault_pair
    mock_summarize.return_value = Summary(title="Test", tldr="t")
    result = ingest(chatgpt_export_path, brain_root=brain, private_root=private, api_key="test")
    assert len(result) == 1
    assert (private / "chat-history" / "chatgpt").exists()
    assert (brain / "_inbox" / "chatgpt").exists()


def test_ingest_unknown_format_raises(
    tmp_path: Path,
    tmp_vault_pair: tuple[Path, Path],
) -> None:
    brain, private = tmp_vault_pair
    bogus = tmp_path / "bogus.txt"
    bogus.write_text("not an export")
    try:
        ingest(bogus, brain_root=brain, private_root=private, api_key="test")
    except ValueError as e:
        assert "format" in str(e).lower() or "unknown" in str(e).lower()
    else:
        raise AssertionError("Should have raised ValueError for unknown format")
