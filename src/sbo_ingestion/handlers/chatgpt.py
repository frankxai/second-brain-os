"""ChatGPT conversation export parser.

ChatGPT exports as either one ``conversations.json`` file or a ZIP containing
``conversations.json`` / numbered ``conversations-000.json`` shards. Each member is
a JSON array of conversation objects. Each conversation has a `mapping` dict that's
a tree of messages (parent/children pointers). The author role is
`user | assistant | system | tool`. Preserve the graph in a versioned envelope;
legacy messages are a selected-branch user/assistant projection.
"""

from __future__ import annotations

import json
import re
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from hashlib import file_digest, sha256
from pathlib import Path, PurePosixPath
from zipfile import BadZipFile, ZipFile

from sbo_ingestion.handlers.chatgpt_source import ChatGPTSource, canonical_json, content_text
from sbo_ingestion.handlers.claude_ai import Conversation, Message

_CONVERSATION_MEMBER = re.compile(r"^conversations(?:-(\d+))?\.json$")


def parse_export(path: Path, *, account_scope: str | None = None) -> Iterator[Conversation]:
    """Yield conversations from a ChatGPT JSON file or official export ZIP.

    ZIP members are consumed one shard at a time, so the full multi-gigabyte
    export is never extracted or loaded into memory as one corpus.
    """
    if account_scope is not None and (not account_scope.strip() or len(account_scope) > 256):
        raise ValueError("Account scope must be a non-empty bounded opaque identifier")
    with path.open("rb") as raw:
        source_hash = file_digest(raw, "sha256").hexdigest()
    if path.suffix.lower() == ".zip":
        yield from _parse_zip_export(path, account_scope=account_scope, source_hash=source_hash)
        return

    data = json.loads(path.read_bytes())
    yield from _parse_array(
        data,
        source=str(path),
        account_scope=account_scope,
        source_hash=source_hash,
        member=path.name,
        member_hash=source_hash,
    )


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
                        raise ValueError(f"Conversation member must be at ZIP root, got {name}")
                    shard = int(match.group(1)) if match.group(1) is not None else None
                    matches.append((shard, name))
    except BadZipFile as exc:
        raise ValueError(f"Invalid ZIP export: {path}") from exc

    legacy = tuple(name for shard, name in matches if shard is None)
    shards = [(shard, name) for shard, name in matches if shard is not None]
    if legacy and shards:
        raise ValueError("Ambiguous ChatGPT export: found conversations.json and numbered shards")
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


def _parse_zip_export(
    path: Path, *, account_scope: str | None, source_hash: str
) -> Iterator[Conversation]:
    members = conversation_members(path)
    if not members:
        raise ValueError(f"No conversations.json or conversations-NNN.json members found in {path}")

    with ZipFile(path) as archive:
        seen_ids: set[str] = set()
        for member in members:
            payload = archive.read(member)
            data = json.loads(payload)
            member_hash = sha256(payload).hexdigest()
            del payload
            for conversation in _parse_array(
                data,
                source=f"{path}!{member}",
                account_scope=account_scope,
                source_hash=source_hash,
                member=member,
                member_hash=member_hash,
            ):
                if conversation.uuid in seen_ids:
                    raise ValueError(
                        f"Duplicate conversation ID across ZIP shards: {conversation.uuid}"
                    )
                seen_ids.add(conversation.uuid)
                yield conversation


def _parse_array(
    data: object,
    *,
    source: str,
    account_scope: str | None,
    source_hash: str,
    member: str,
    member_hash: str,
) -> Iterator[Conversation]:
    if not isinstance(data, list):
        raise ValueError(f"Expected top-level JSON array in {source}, got {type(data).__name__}")
    seen_ids = set()
    for obj in data:
        if not isinstance(obj, dict):
            raise ValueError(f"Expected conversation object in {source}, got {type(obj).__name__}")
        identity = obj.get("id")
        if not isinstance(identity, str) or not identity.strip():
            raise ValueError("Conversation ID must be a non-empty string")
        if identity in seen_ids:
            raise ValueError("Duplicate conversation ID in export member")
        conversation = _parse_conversation(
            obj,
            account_scope=account_scope,
            source_sha256=source_hash,
            member=member,
            member_sha256=member_hash,
        )
        seen_ids.add(conversation.uuid)
        yield conversation


def _epoch_to_iso(ts: object | None) -> str:
    if isinstance(ts, bool) or not isinstance(ts, (int, float)):
        return ""
    try:
        # Avoid platform-specific ``fromtimestamp`` range failures on Windows.
        # Official exports occasionally contain outlier timestamps; retain the
        # conversation and omit only the invalid metadata value.
        return (datetime(1970, 1, 1, tzinfo=UTC) + timedelta(seconds=ts)).isoformat()
    except (OverflowError, ValueError):
        return ""


def _parse_conversation(obj: dict, **provenance) -> Conversation:
    if not isinstance(obj.get("id"), str) or not obj["id"].strip():
        raise ValueError("Conversation ID must be a non-empty string")
    mapping = obj.get("mapping", {})
    if not isinstance(mapping, dict):
        raise ValueError("ChatGPT mapping must be an object")
    for node in mapping.values():
        if not isinstance(node, dict) or not isinstance(node.get("children", []), list):
            raise ValueError("Invalid ChatGPT node")
        if node.get("parent") is not None and not isinstance(node["parent"], str):
            raise ValueError("Invalid ChatGPT parent")
        if any(not isinstance(child, str) for child in node.get("children", [])):
            raise ValueError("Invalid ChatGPT children")
        if node.get("message") is not None and not isinstance(node["message"], dict):
            raise ValueError("Invalid ChatGPT message")
        msg = node.get("message")
        if msg is not None:
            if msg.get("id") is not None and not isinstance(msg["id"], str):
                raise ValueError("Invalid ChatGPT message ID")
            author = msg.get("author")
            content = msg.get("content")
            if author is not None and not isinstance(author, dict):
                raise ValueError("Invalid ChatGPT author")
            if content is not None and not isinstance(content, dict):
                raise ValueError("Invalid ChatGPT content")
            if (
                isinstance(content, dict)
                and content.get("parts") is not None
                and not isinstance(content["parts"], list)
            ):
                raise ValueError("Invalid ChatGPT content parts")
    if obj.get("current_node") is not None and not isinstance(obj["current_node"], str):
        raise ValueError("Invalid ChatGPT current node")
    graph = ChatGPTSource(original_json=canonical_json(obj), **provenance)
    messages: list[Message] = []
    for key in graph.path_to():
        msg = mapping[key].get("message")
        if not msg:
            continue
        author = (msg.get("author") or {}).get("role")
        text = content_text(msg)
        if author not in ("user", "assistant") or not text:
            continue
        messages.append(
            Message(
                uuid=msg.get("id") or key,
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
        source_graph=graph,
    )
