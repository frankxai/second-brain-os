"""Claude.ai JSONL export parser.

Claude.ai exports are JSON Lines: one conversation per line, top-level object with
`uuid`, `name`, `created_at`, `updated_at`, `chat_messages` (array). Each message has
`uuid`, `text`, `sender` (human|assistant), `created_at`.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator


@dataclass(frozen=True)
class Message:
    uuid: str
    sender: str  # "human" | "assistant"
    text: str
    created_at: str


@dataclass(frozen=True)
class Conversation:
    uuid: str
    title: str
    created_at: str
    updated_at: str
    messages: tuple[Message, ...]
    platform: str = "claude.ai"

    def to_raw_markdown(self) -> str:
        """Render this conversation as the raw-vault markdown body (no frontmatter).

        Frontmatter is added by dual_write.py, which knows the storage location.
        """
        lines: list[str] = [f"# {self.title}", ""]
        for m in self.messages:
            lines.append(f"**{m.sender}** · {m.created_at}")
            lines.append("")
            lines.append(m.text)
            lines.append("")
        return "\n".join(lines).rstrip() + "\n"


def parse_export(path: Path) -> Iterator[Conversation]:
    """Yield Conversation objects from a Claude.ai JSONL export file."""
    with path.open("r", encoding="utf-8") as f:
        for line_num, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError as e:
                raise ValueError(f"Invalid JSON on line {line_num} of {path}: {e}") from e
            yield _parse_conversation(obj)


def _parse_conversation(obj: dict) -> Conversation:
    messages = tuple(
        Message(
            uuid=m["uuid"],
            sender=m["sender"],
            text=m["text"],
            created_at=m["created_at"],
        )
        for m in obj.get("chat_messages", [])
    )
    return Conversation(
        uuid=obj["uuid"],
        title=obj.get("name", "Untitled"),
        created_at=obj["created_at"],
        updated_at=obj.get("updated_at", obj["created_at"]),
        messages=messages,
    )
