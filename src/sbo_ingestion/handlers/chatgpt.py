"""ChatGPT conversations.json export parser.

ChatGPT exports as a JSON array of conversation objects. Each conversation has a
`mapping` dict that's a tree of messages (parent/children pointers). The author role
is `user | assistant | system | tool`. We flatten the tree by walking from each
root child in chronological order, and we collapse system+tool messages.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator

from sbo_ingestion.handlers.claude_ai import Conversation, Message


def parse_export(path: Path) -> Iterator[Conversation]:
    """Yield Conversation objects from a ChatGPT conversations.json export file."""
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, list):
        raise ValueError(
            f"Expected top-level JSON array in {path}, got {type(data).__name__}"
        )
    for obj in data:
        yield _parse_conversation(obj)


def _epoch_to_iso(ts: float | None) -> str:
    if ts is None:
        return ""
    return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()


def _walk_mapping(mapping: dict) -> list[dict]:
    """Flatten the message tree by chronological create_time across all nodes."""
    nodes: list[dict] = []
    for node in mapping.values():
        msg = node.get("message")
        if not msg:
            continue
        nodes.append(node)
    nodes.sort(key=lambda n: (n["message"].get("create_time") or 0))
    return nodes


def _parse_conversation(obj: dict) -> Conversation:
    mapping = obj.get("mapping", {})
    raw_messages = _walk_mapping(mapping)
    messages: list[Message] = []
    for node in raw_messages:
        msg = node["message"]
        author = (msg.get("author") or {}).get("role")
        if author not in ("user", "assistant"):
            continue  # skip system, tool, role-less
        parts = (msg.get("content") or {}).get("parts") or []
        text = "\n\n".join(str(p) for p in parts if p).strip()
        if not text:
            continue
        messages.append(
            Message(
                uuid=msg["id"],
                sender="human" if author == "user" else "assistant",
                text=text,
                created_at=_epoch_to_iso(msg.get("create_time")),
            )
        )
    return Conversation(
        uuid=obj["id"],
        title=obj.get("title") or "Untitled",
        created_at=_epoch_to_iso(obj.get("create_time")),
        updated_at=_epoch_to_iso(obj.get("update_time") or obj.get("create_time")),
        messages=tuple(messages),
        platform="chatgpt",
    )
