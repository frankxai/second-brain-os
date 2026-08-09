"""ChatGPT conversation export parser.

ChatGPT exports as either one ``conversations.json`` file or a ZIP containing
``conversations.json`` / numbered ``conversations-000.json`` shards. Each member is
a JSON array of conversation objects. Each conversation has a `mapping` dict that's
a tree of messages (parent/children pointers). The author role is
`user | assistant | system | tool`. We flatten the tree by walking from each root
child in chronological order, and we collapse system+tool messages.
"""

from __future__ import annotations

import json
import re
from collections.abc import Iterator
from datetime import UTC, datetime
from io import TextIOWrapper
from pathlib import Path, PurePosixPath
from zipfile import BadZipFile, ZipFile

from sbo_ingestion.handlers.claude_ai import Conversation, Message

_CONVERSATION_MEMBER = re.compile(r"^conversations(?:-(\d+))?\.json$")


def parse_export(path: Path) -> Iterator[Conversation]:
    """Yield conversations from a ChatGPT JSON file or official export ZIP.

    ZIP members are consumed one shard at a time, so the full multi-gigabyte
    export is never extracted or loaded into memory as one corpus.
    """
    if path.suffix.lower() == ".zip":
        yield from _parse_zip_export(path)
        return

    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    yield from _parse_array(data, source=str(path))


def conversation_members(path: Path) -> tuple[str, ...]:
    """Return the canonical conversation member(s) in an official export ZIP.

    Accept exactly one top-level legacy member or one contiguous numbered shard
    set. Ambiguous, nested, duplicated, or gapped layouts are rejected instead
    of guessing and silently omitting data. ``shared_conversations.json`` is
    intentionally excluded.
    """
    try:
        with ZipFile(path) as archive:
            matches: list[tuple[int | None, str]] = []
            for name in archive.namelist():
                member_path = PurePosixPath(name)
                basename = member_path.name
                match = _CONVERSATION_MEMBER.fullmatch(basename)
                if match:
                    if len(member_path.parts) != 1:
                        raise ValueError(
                            f"Conversation member must be at ZIP root, got {name}"
                        )
                    shard = int(match.group(1)) if match.group(1) is not None else None
                    matches.append((shard, name))
    except BadZipFile as exc:
        raise ValueError(f"Invalid ZIP export: {path}") from exc

    legacy = tuple(name for shard, name in matches if shard is None)
    shards = [(shard, name) for shard, name in matches if shard is not None]
    if legacy and shards:
        raise ValueError(
            "Ambiguous ChatGPT export: found conversations.json and numbered shards"
        )
    if legacy:
        if len(legacy) != 1:
            raise ValueError("Ambiguous ChatGPT export: duplicate conversations.json members")
        return legacy
    if not shards:
        return ()

    indexes = [shard for shard, _ in shards]
    if len(indexes) != len(set(indexes)):
        raise ValueError("Ambiguous ChatGPT export: duplicate numbered shard indexes")
    ordered = sorted(shards, key=lambda item: item[0])
    expected = list(range(len(ordered)))
    actual = [shard for shard, _ in ordered]
    if actual != expected:
        raise ValueError(
            f"Incomplete ChatGPT export: expected shard indexes {expected}, got {actual}"
        )
    return tuple(name for _, name in ordered)


def _parse_zip_export(path: Path) -> Iterator[Conversation]:
    members = conversation_members(path)
    if not members:
        raise ValueError(
            f"No conversations.json or conversations-NNN.json members found in {path}"
        )

    with ZipFile(path) as archive:
        seen_ids: set[str] = set()
        for member in members:
            with archive.open(member) as raw, TextIOWrapper(raw, encoding="utf-8") as f:
                data = json.load(f)
            for conversation in _parse_array(data, source=f"{path}!{member}"):
                if conversation.uuid in seen_ids:
                    raise ValueError(
                        f"Duplicate conversation ID across ZIP shards: {conversation.uuid}"
                    )
                seen_ids.add(conversation.uuid)
                yield conversation


def _parse_array(data: object, *, source: str) -> Iterator[Conversation]:
    if not isinstance(data, list):
        raise ValueError(
            f"Expected top-level JSON array in {source}, got {type(data).__name__}"
        )
    for obj in data:
        if not isinstance(obj, dict):
            raise ValueError(
                f"Expected conversation object in {source}, got {type(obj).__name__}"
            )
        yield _parse_conversation(obj)


def _epoch_to_iso(ts: float | None) -> str:
    if ts is None:
        return ""
    return datetime.fromtimestamp(ts, tz=UTC).isoformat()


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
