"""Pytest fixtures shared across SBO ingestion tests."""

from __future__ import annotations

from pathlib import Path

import pytest


FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def claude_ai_export_path() -> Path:
    """Path to a small Claude.ai export fixture (JSONL)."""
    return FIXTURES_DIR / "claude-ai-export-sample.jsonl"


@pytest.fixture
def chatgpt_export_path() -> Path:
    """Path to a small ChatGPT conversations.json fixture."""
    return FIXTURES_DIR / "chatgpt-conversations-sample.json"


@pytest.fixture
def tmp_vault_pair(tmp_path: Path) -> tuple[Path, Path]:
    """Create empty brain/ and private/ vault skeletons in a tmp dir.

    Returns (brain_root, private_root).
    """
    brain = tmp_path / "brain"
    private = tmp_path / "private"
    (brain / "_inbox" / "claude-ai").mkdir(parents=True)
    (brain / "_inbox" / "chatgpt").mkdir(parents=True)
    (private / "chat-history" / "claude-ai").mkdir(parents=True)
    (private / "chat-history" / "chatgpt").mkdir(parents=True)
    return brain, private
