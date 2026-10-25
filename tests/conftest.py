"""Pytest fixtures shared across SBO ingestion tests."""

from __future__ import annotations

import json
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
def memories_list_path() -> Path:
    """Path to a memories.json fixture in top-level-list shape."""
    return FIXTURES_DIR / "memories-list-sample.json"


@pytest.fixture
def memories_dict_path() -> Path:
    """Path to a memories.json fixture in wrapper-dict shape."""
    return FIXTURES_DIR / "memories-dict-sample.json"


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


@pytest.fixture
def chatgpt_sharded_dir() -> Path:
    """Directory holding a 2-shard ChatGPT export (conversations-000/001.json)."""
    return FIXTURES_DIR / "chatgpt-sharded"


@pytest.fixture
def claude_ai_json_export_path() -> Path:
    """Path to an array-shaped Claude.ai export fixture (.json, not JSONL)."""
    return FIXTURES_DIR / "claude-ai-export-sample.json"


@pytest.fixture
def branched_export(tmp_path):
    def node(key, parent, children, role, text, time):
        return {
            "id": key,
            "parent": parent,
            "children": children,
            "message": {
                "id": "message-" + key,
                "author": {"role": role},
                "create_time": time,
                "content": {"parts": [text]},
                "recipient": "python" if key == "call" else "all",
                "metadata": {"tool_call_id": "call-1"} if role == "tool" else {},
            },
        }

    mapping = {
        "root": {"id": "root", "parent": None, "children": ["system"], "message": None},
        "system": node("system", "root", ["u1", "u2"], "system", "policy as data", 1),
        "u1": node("u1", "system", ["a1"], "user", "original prompt", 2),
        "a1": node("a1", "u1", [], "assistant", "alternate answer", 99),
        "u2": node("u2", "system", ["call"], "user", "edited prompt", 3),
        "call": node("call", "u2", ["tool"], "assistant", "tool invocation", 20),
        "tool": node("tool", "call", ["a2"], "tool", "tool result", 10),
        "a2": node("a2", "tool", [], "assistant", "selected answer", 4),
    }
    source = {
        "id": "synthetic-conversation",
        "title": "Synthetic branches",
        "create_time": 1,
        "current_node": "a2",
        "mapping": mapping,
    }
    path = tmp_path / "conversations.json"
    path.write_text(json.dumps([source]), encoding="utf-8")
    return path
