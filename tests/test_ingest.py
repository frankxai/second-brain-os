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


def test_ingest_dry_run_skips_api(
    claude_ai_export_path: Path,
    tmp_vault_pair: tuple[Path, Path],
) -> None:
    """Dry-run must not call the Anthropic API and must still produce both files."""
    brain, private = tmp_vault_pair
    # No api_key, no mock — proves no network call happens.
    result = ingest(
        claude_ai_export_path,
        brain_root=brain,
        private_root=private,
        dry_run=True,
    )
    assert len(result) == 2
    assert all(r.private_path.exists() for r in result)
    assert all(r.brain_path.exists() for r in result)
    # Stub-summary marker visible in brain output
    sample = result[0].brain_path.read_text(encoding="utf-8")
    assert "dry-run" in sample.lower()


def test_ingest_requires_api_key_unless_dry_run(
    claude_ai_export_path: Path,
    tmp_vault_pair: tuple[Path, Path],
) -> None:
    """Without dry_run and without an api_key, ingest must raise — never silently call Anthropic."""
    brain, private = tmp_vault_pair
    try:
        ingest(claude_ai_export_path, brain_root=brain, private_root=private)
    except ValueError as e:
        assert "api_key" in str(e).lower()
    else:
        raise AssertionError("Should have raised ValueError when api_key missing")
